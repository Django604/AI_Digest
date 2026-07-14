# Preserve Source Workbook Modified Times in CI

## Goal

Ensure the deployed dashboard displays the source workbook modification times recorded by the local build and committed in `docs/data/dashboard.json` and `docs/data/dashboard.summary.json`. GitHub Actions must not replace those values with checkout-time file metadata from its UTC runner.

## Design

Add an opt-in `--preserve-input-modified-times` flag to `scripts/build_dashboard.py`. The default local build behavior remains unchanged: it reads each workbook's filesystem `mtime` and writes it as an ISO timestamp.

When the flag is enabled, the builder reads the existing output JSON before rebuilding and preserves:

- `dashboard.json.meta.workbookModifiedAt`
- `dashboard.summary.json.inputs.workbookModifiedAt`
- `dashboard.summary.json.inputs.arrivalWorkbookModifiedAt`

The preserved leads timestamp must remain consistent between dashboard and summary output. Missing, malformed, or inconsistent committed timestamps cause the build to fail with a clear error instead of silently falling back to CI filesystem times.

The GitHub Pages workflow enables the flag. Local rebuild, scheduled update, and publishing commands do not enable it, so they continue capturing the actual local workbook modification times before committing the generated files.

## Data Flow

1. A local update modifies the Excel workbooks.
2. The local builder reads their actual filesystem modification times and commits those values in the dashboard artifacts.
3. GitHub Actions checks out the commit.
4. The CI builder loads the committed timestamps, rebuilds dashboard content from Excel, and injects the preserved timestamps into regenerated artifacts.
5. Pages deploys artifacts whose displayed source update time matches the local commit.

## Error Handling

Preservation mode requires both existing output files and all expected timestamp fields. Values must be non-empty ISO local datetime strings. The leads timestamp in dashboard and summary must match. Any validation failure terminates the build so a misleading timestamp cannot be deployed.

## Testing

Add focused tests that verify:

- Default builds continue using workbook filesystem modification times.
- Preservation mode keeps committed leads and arrival timestamps even when workbook `mtime` values differ.
- Preservation mode rejects missing or inconsistent committed timestamp metadata.
- The workflow invokes the builder with `--preserve-input-modified-times`.

Run the focused builder tests, Python compilation, and the full unit test suite.

## Scope

No frontend changes are required. The page continues rendering `meta.workbookModifiedAt` by replacing `T` with a space. No timezone conversion is introduced because the desired value is the locally recorded timestamp itself.
