# Changelog

## Unreleased — 2026-10-23

### Repository baseline

- Fast-forwarded local `master` to the current remote tip (`1c5684a`). Pull request
  #3 had already merged all changes from `alvaro/refactor-and-add-more-cuotas`;
  no branch work is currently missing from `master`.
- Kept the rename from `master` to `main` as a separate final step after these
  changes have been reviewed and committed.

### Tooling

- Moved `ruff` and `pre-commit` out of runtime dependencies and added
  `pytest` and `ty` to a development dependency group.
- Configured Ruff with Python 3.13 targeting, import sorting, style checks, and
  a broader safety-focused rule set.
- Configured ty with the project's Python version and stricter checks for
  missing type arguments and unsound assignments/returns.
- Added local pre-commit hooks for Ruff linting, Ruff formatting, ty, and pytest.
  The hook is installed in this checkout.

**Impact:** production installs no longer carry development-only tooling, while
linting, formatting, type errors, and unit-test failures are caught before code
is committed.

### Application code

- Added type annotations and Google Sheets types to the workbook-processing and
  upload functions.
- Added function docstrings and extracted `prepare_movements()` so normalization
  can be tested independently from Streamlit and Google Sheets.
- Wrapped the Streamlit UI in a typed `main()` entry point.
- Added a clear error when one of the expected destination worksheets is absent.

**Impact:** the main transformation boundary is easier to test and reason about,
and invalid interfaces are now visible to ty.

### Bug fixes

- Fixed the call to `Worksheet.update()` for the fee worksheet. The range (`B1`)
  and cell values had been passed in the reverse order accepted by gspread.

**Impact:** uploading the calculated fee table no longer fails because of the
invalid argument order.

### Tests

- Added unit tests for column normalization, movement classification, fee
  aggregation, empty fee results, and the fee-table upload range.

**Impact:** the current financial transformation contract is covered before
future functionality changes begin.

### Documentation and repository hygiene

- Updated the README with the actual Python requirement, `uv` workflow, secret
  format, Streamlit command, quality commands, and project layout.
- Added explicit local ignores for Python bytecode, pytest, Ruff, and virtual
  environment caches.

**Impact:** a contributor can install, configure, run, and validate the project
from the repository documentation, without committing generated files.

### Verification

- Ruff lint: passed.
- Ruff format check: passed.
- ty check: passed.
- pytest: 4 tests passed.
- pre-commit: all four hooks passed.
- Streamlit headless startup: passed at `http://localhost:8765`.

### Follow-up improvement areas

1. Define the workbook schema as typed records and validate required columns,
   date formats, and amounts at the boundary.
2. Clarify fee counting when a member pays multiple fees in one month; the
   current pivot counts occupied months, not necessarily individual payments.
3. Replace the four-sheet positional upload with explicit sheet names and clear
   size/range handling.
4. Add integration tests with representative workbooks and mocked Google Sheets
   responses, including partial failures and retries.
5. Add user-facing validation and errors for unreadable files, malformed
   concepts, missing secrets, and unavailable worksheets.
6. Add CI to run pre-commit on pushes and pull requests after the default branch
   has been moved to `main`.
