"""Google Drive storage for generated invoices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any, cast

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from invoicing.models import Reservation
from invoicing.naming import (
    build_invoice_name,
    extract_invoice_number,
    invoice_pdf_filename,
    invoice_quarter,
    quarter_folder_name,
    year_folder_name,
)
from invoicing.pdf import build_invoice_pdf

INVOICE_ROOT_FOLDER_ID = "0B8-aV0rAOsvpRjE4dVBkYXNheG8"
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_EMITTED_NAMES = {
    "facturas emitidas (ingresos)",
    "factura emitidas (ingresos)",
}
_QUARTER_PATTERN = re.compile(r"^GEM IVA ([1-4])T (\d{4})$")


@dataclass(frozen=True, slots=True)
class InvoiceCreation:
    number: int
    name: str
    folder_id: str
    folder_url: str
    already_exists: bool


class InvoiceDriveStore:
    """Read the current sequence and create invoices in the shared Drive."""

    def __init__(
        self,
        service: Any,
        *,
        root_folder_id: str = INVOICE_ROOT_FOLDER_ID,
    ) -> None:
        self._service = service
        self._root_folder_id = root_folder_id

    @classmethod
    def from_service_account(
        cls,
        credentials: dict[str, Any],
        *,
        root_folder_id: str = INVOICE_ROOT_FOLDER_ID,
    ) -> InvoiceDriveStore:
        google_credentials = service_account.Credentials.from_service_account_info(
            credentials,
            scopes=[_DRIVE_SCOPE],
        )
        service = build(
            "drive",
            "v3",
            credentials=google_credentials,
            cache_discovery=False,
        )
        return cls(service, root_folder_id=root_folder_id)

    def next_invoice_number(self, invoice_date: date) -> int:
        year_folder = self._find_child_folder(
            self._root_folder_id,
            year_folder_name(invoice_date),
        )
        if year_folder is None:
            return 1

        numbers: list[int] = []
        for folder in self._list_child_folders(year_folder["id"]):
            match = _QUARTER_PATTERN.fullmatch(str(folder.get("name", "")))
            if match is None or int(match.group(2)) != invoice_date.year:
                continue
            emitted = self._find_emitted_folder(str(folder["id"]))
            if emitted is None:
                continue
            for invoice_folder in self._list_child_folders(emitted["id"]):
                number = extract_invoice_number(
                    str(invoice_folder.get("name", "")),
                    invoice_date.year,
                )
                if number is not None:
                    numbers.append(number)
        return max(numbers, default=0) + 1

    def create_invoice(
        self,
        reservation: Reservation,
        *,
        invoice_date: date,
    ) -> InvoiceCreation:
        existing = self._find_by_hash(reservation.reservation_hash)
        if existing is not None:
            number = self._invoice_number_from_metadata(existing, invoice_date.year)
            if existing.get("appProperties", {}).get("invoice_status") == "complete":
                return InvoiceCreation(
                    number=number,
                    name=str(existing["name"]),
                    folder_id=str(existing["id"]),
                    folder_url=str(existing["webViewLink"]),
                    already_exists=True,
                )
            return self._finish_existing_folder(
                existing,
                reservation,
                invoice_date=invoice_date,
                number=number,
            )

        number = self.next_invoice_number(invoice_date)
        name = build_invoice_name(
            alias=reservation.alias,
            starts_on=reservation.starts_on,
            ends_on=reservation.ends_on,
            refuge=reservation.refuge,
            number=number,
            invoice_date=invoice_date,
        )
        pdf_bytes = build_invoice_pdf(
            reservation,
            number=number,
            invoice_date=invoice_date,
        )
        target_id = self._ensure_invoice_folder(invoice_date)
        properties = self._properties(
            reservation,
            number=number,
            status="pending_upload",
            invoice_date=invoice_date,
        )
        folder = (
            self._service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": _FOLDER_MIME_TYPE,
                    "parents": [target_id],
                    "appProperties": properties,
                },
                fields="id,name,webViewLink,appProperties",
                supportsAllDrives=True,
            )
            .execute(num_retries=2)
        )
        folder_id = str(folder["id"])
        self._upload_pdf(
            folder_id,
            invoice_pdf_filename(name),
            pdf_bytes,
            properties,
        )
        complete_properties = dict(properties)
        complete_properties["invoice_status"] = "complete"
        self._update_properties(folder_id, complete_properties)
        return InvoiceCreation(
            number=number,
            name=name,
            folder_id=folder_id,
            folder_url=str(folder["webViewLink"]),
            already_exists=False,
        )

    def _finish_existing_folder(
        self,
        existing: dict[str, Any],
        reservation: Reservation,
        *,
        invoice_date: date,
        number: int,
    ) -> InvoiceCreation:
        folder_id = str(existing["id"])
        name = str(existing["name"])
        children = self._list_children(folder_id)
        if any(child.get("mimeType") == "application/pdf" for child in children):
            complete_properties = {
                **cast(dict[str, str], existing.get("appProperties", {})),
                "invoice_status": "complete",
            }
            self._update_properties(folder_id, complete_properties)
            return InvoiceCreation(
                number=number,
                name=name,
                folder_id=folder_id,
                folder_url=str(existing["webViewLink"]),
                already_exists=True,
            )

        pdf_bytes = build_invoice_pdf(
            reservation,
            number=number,
            invoice_date=invoice_date,
        )
        properties = cast(dict[str, str], existing.get("appProperties", {}))
        self._upload_pdf(
            folder_id,
            invoice_pdf_filename(name),
            pdf_bytes,
            properties,
        )
        complete_properties = {
            **properties,
            "invoice_status": "complete",
        }
        self._update_properties(folder_id, complete_properties)
        return InvoiceCreation(
            number=number,
            name=name,
            folder_id=folder_id,
            folder_url=str(existing["webViewLink"]),
            already_exists=False,
        )

    def _ensure_invoice_folder(self, invoice_date: date) -> str:
        year_folder = self._find_or_create_child(
            self._root_folder_id,
            year_folder_name(invoice_date),
        )
        quarter_folder = self._find_or_create_child(
            str(year_folder["id"]),
            quarter_folder_name(invoice_date),
        )
        emitted = self._find_emitted_folder(str(quarter_folder["id"]))
        if emitted is not None:
            return str(emitted["id"])
        created = self._create_folder(
            str(quarter_folder["id"]),
            "Facturas emitidas (ingresos)",
        )
        return str(created["id"])

    def _find_emitted_folder(self, parent_id: str) -> dict[str, Any] | None:
        for folder in self._list_child_folders(parent_id):
            if str(folder.get("name", "")).casefold() in _EMITTED_NAMES:
                return folder
        return None

    def _find_or_create_child(
        self,
        parent_id: str,
        name: str,
    ) -> dict[str, Any]:
        existing = self._find_child_folder(parent_id, name)
        if existing is not None:
            return existing
        return self._create_folder(parent_id, name)

    def _find_child_folder(
        self,
        parent_id: str,
        name: str,
    ) -> dict[str, Any] | None:
        for folder in self._list_child_folders(parent_id):
            if str(folder.get("name", "")).casefold() == name.casefold():
                return folder
        return None

    def _create_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        return (
            self._service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": _FOLDER_MIME_TYPE,
                    "parents": [parent_id],
                },
                fields="id,name,webViewLink",
                supportsAllDrives=True,
            )
            .execute(num_retries=2)
        )

    def _list_child_folders(self, parent_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self._list_children(parent_id)
            if item.get("mimeType") == _FOLDER_MIME_TYPE
        ]

    def _list_children(self, parent_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request = self._service.files().list(
                q=f"'{parent_id}' in parents and trashed=false",
                fields=(
                    "nextPageToken,files(id,name,mimeType,webViewLink,appProperties)"
                ),
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            response = request.execute(num_retries=2)
            items.extend(cast(list[dict[str, Any]], response.get("files", [])))
            page_token = cast(str | None, response.get("nextPageToken"))
            if not page_token:
                return items

    def _find_by_hash(self, reservation_hash: str) -> dict[str, Any] | None:
        query = (
            "appProperties has { key='reservation_hash' and "
            f"value='{reservation_hash}' }} and trashed=false"
        )
        response = (
            self._service.files()
            .list(
                q=query,
                fields=("files(id,name,mimeType,webViewLink,appProperties)"),
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute(num_retries=2)
        )
        for item in response.get("files", []):
            if item.get("mimeType") == _FOLDER_MIME_TYPE:
                return cast(dict[str, Any], item)
        return None

    def _invoice_number_from_metadata(
        self,
        folder: dict[str, Any],
        year: int,
    ) -> int:
        metadata_number = folder.get("appProperties", {}).get("invoice_number")
        if metadata_number is not None:
            return int(metadata_number)
        number = extract_invoice_number(str(folder.get("name", "")), year)
        if number is None:
            raise ValueError("Existing invoice folder has no recognisable number.")
        return number

    def _upload_pdf(
        self,
        folder_id: str,
        name: str,
        pdf_bytes: bytes,
        properties: dict[str, str],
    ) -> None:
        media = MediaIoBaseUpload(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            resumable=False,
        )
        (
            self._service.files()
            .create(
                body={
                    "name": name,
                    "parents": [folder_id],
                    "appProperties": {
                        "reservation_hash": properties["reservation_hash"],
                        "invoice_number": properties["invoice_number"],
                    },
                },
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute(num_retries=2)
        )

    def _update_properties(
        self,
        folder_id: str,
        properties: dict[str, str],
    ) -> None:
        (
            self._service.files()
            .update(
                fileId=folder_id,
                body={"appProperties": properties},
                fields="id",
                supportsAllDrives=True,
            )
            .execute(num_retries=2)
        )

    @staticmethod
    def _properties(
        reservation: Reservation,
        *,
        number: int,
        status: str,
        invoice_date: date,
    ) -> dict[str, str]:
        return {
            "reservation_hash": reservation.reservation_hash,
            "invoice_number": str(number),
            "invoice_status": status,
            "invoice_quarter": str(invoice_quarter(invoice_date)),
            "refuge": reservation.refuge.short_name,
        }
