# Changelog

## Unreleased — 2026-10-23

### Repository baseline

- Fast-forwarded local `master` to the current remote tip (`1c5684a`). Pull request
  #3 had already merged all changes from `alvaro/refactor-and-add-more-cuotas`;
  no branch work is currently missing from `master`.

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

### Member matching

- Added a private, read-only member directory with one row per member and
  spreadsheet-friendly alias columns.
- Added accent, punctuation, casing, and whitespace normalization before matching.
- Consolidated aliases to canonical member names and reported unmatched or
  ambiguous fee-like transfers.
- Added cross-member similarity validation so an alias resembling another member
  is blocked instead of silently matching the wrong person.
- Sorted fee rows alphabetically using accent-insensitive keys while preserving
  the original accented display names.
- Added configurable 12-month inactivity and 3-month single-payment grace rules.
- Removed manual fee-name columns from overwrite handling; uploads now clear stale
  rows and write the generated table from column A.

**Impact:** name variants no longer create duplicate fee rows, old or isolated
payments are excluded with notices, and the generated name column cannot drift
from the member directory.

### Financial report

- Added a formula-driven `Informe` worksheet with editable `Desde` and `Hasta`
  date controls.
- Added dynamic totals for member fees, other income, total income, costs, and
  net balance.
- Added a monthly evolution table and a formula-driven top-15 expense query.
- Added expense categories stored in `General` and `Gastos`, including distinct
  rent and electricity classification for the two Canal de Isabel II concepts.
- Added category totals and kept a single overall expense ranking.
- Added income-share percentages for fees versus other income and expense-share
  percentages for every expense category.
- Changed report filtering from month-only comparisons to exact `Desde`/`Hasta`
  dates, including partial first and last months.
- Added a non-destructive layout migration that copies existing formatting when
  shifting the expense table to accommodate the new percentage columns.
- Switched output updates from positional worksheet indexes to explicit tab
  names so inserting `Informe` cannot move data into the wrong sheets.
- Removed the redundant `Gastos`, `Ingresos`, and `Tabla dinámica 2` sheets from
  the output workflow; `General` remains the single movement source of truth.
- Moved the top-15 ranking beside the visible summary blocks and enforce
  `Informe` as the second worksheet.
- Made formulas locale-aware so Spanish Google Sheets accounts use semicolon
  argument separators.

**Impact:** the report can be explored and recalculated directly in Google Sheets
without running Streamlit after its initial creation.

### Project exclusions

- Added stable transaction IDs and preserved bank references in processed data.
- Added a persistent `Marshill (Sudáfrica)` ledger that the application only
  reads during normal processing.
- Excluded project transactions before member matching, fee summaries, expense
  categories, and all report formulas.

**Impact:** project costs and reimbursements can be removed from every financial
total while remaining available in their own ledger.

### Operations

- Added `scripts/regenerate_production.py` to regenerate the configured
  production workbook from the newest private bank export.

### Bug fixes

- Fixed the call to `Worksheet.update()` for the fee worksheet. The range (`B1`)
  and cell values had been passed in the reverse order accepted by gspread.

**Impact:** uploading the calculated fee table no longer fails because of the
invalid argument order.

### Tests

- Added synthetic-data unit tests for member matching, alias ambiguity, movement
  classification, fee eligibility, empty results, and full-range uploads.

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
- pytest: 29 tests passed.
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
6. Add CI to run pre-commit on pushes and pull requests targeting `master`.
