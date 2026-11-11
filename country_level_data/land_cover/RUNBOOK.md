# Land Cover Runbook

Practical commands for downloading, mosaicking, and clipping datasets in this folder.
Run all commands from `country_level_data/`. Order: export (GEE) → monitor → download (rclone) → mosaic → bias-correct.

## WorldCover export (GEE)

```bash
python3 land_cover/export_worldcover_idn_mys.py --year 2020
python3 land_cover/export_worldcover_idn_mys.py --year 2021
```

Test region:

```bash
python3 land_cover/export_worldcover_idn_mys.py --year 2020 --test-region
```

Monitor export tasks from the terminal (instead of the Code Editor Tasks tab):

```bash
python3 ../tools/monitor_gee_tasks.py --filter worldcover --wait
```

## GlobalOilPalm YoP (2021) export (GEE)

```bash
python3 land_cover/export_oilpalm_yop_idn_mys.py
```

## Mosaic GlobalOilPalm YoP 2021 tiles to COG

```bash
./land_cover/mosaic_oilpalm_yop_2021.sh
```

## Bias-correct WorldCover 2021 with oil palm YoP

```bash
./land_cover/bias_correct_worldcover_with_oilpalm.sh
```

## Download GlobalOilPalm YoP 2021 tiles (rclone)

```bash
./land_cover/download_oilpalm_yop_tiles.sh --remote "gdrive"
```

## Download WorldCover tiles from Google Drive (rclone)

List remotes:

```bash
rclone listremotes
```

Download tiles (example remote name: `gdrive`):

```bash
./land_cover/download_worldcover_tiles.sh --remote "gdrive" --year 2020
./land_cover/download_worldcover_tiles.sh --remote "gdrive" --year 2021
```

If your rclone config is not in the default location:

```bash
RCLONE_CONFIG=/path/to/rclone.conf ./land_cover/download_worldcover_tiles.sh --remote "gdrive" --year 2020
```

## Mosaic WorldCover tiles to COG

Outputs go to `land_cover/mosaics/`:

```bash
mkdir -p land_cover/mosaics

gdalbuildvrt land_cover/mosaics/worldcover_2020_idn_mys.vrt \
  land_cover/gee_worldcover_2020_idn_mys/*.tif

gdal_translate land_cover/mosaics/worldcover_2020_idn_mys.vrt \
  land_cover/mosaics/worldcover_2020_idn_mys_cog.tif \
  -of COG -co COMPRESS=DEFLATE
```

Repeat for 2021 by swapping the input folder/output names.

## Mosaic GlobalOilPalm YoP to IDN+MYS footprint

Fast mask-based method (recommended, aligns to YoP grid):

```bash
./land_cover/mosaic_oilpalm_idn_mys_mask.sh
```

Alternative cutline method:

```bash
./land_cover/mosaic_oilpalm_idn_mys.sh --use-bbox
```

Override paths if needed:

```bash
./land_cover/mosaic_oilpalm_idn_mys.sh \
  --worldcover land_cover/mosaics/worldcover_2020_idn_mys_cog.tif \
  --oilpalm-dir land_cover/GlobalOilPalm_OP-YoP \
  --out land_cover/mosaics/oilpalm_yop_idn_mys_cog.tif
```
