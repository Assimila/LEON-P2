# LEON Share (country_level_data + company)

Code-only share of key scripts from:
- `country_level_data/`
- `company/`

Large datasets and generated outputs are intentionally excluded.

## Included
- Python and shell scripts
- Runbooks

## Not included
- Raster/vector datasets
- PDFs/CSVs/PNGs and other heavy artifacts
- Secrets or machine-specific paths

## Environment
Recommended:
- Python 3.10+
- GDAL utilities (`gdalbuildvrt`, `gdal_translate`, `gdalwarp`)
- `rclone` (for sync/download scripts)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Notes
- Script defaults were made portable using each script's local directory.
- You can always override paths via CLI flags.
