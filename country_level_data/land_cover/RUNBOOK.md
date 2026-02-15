# Land Cover Runbook

Practical commands for downloading, mosaicking, and clipping datasets in this folder.

## WorldCover export (GEE)

Run from repo root:

```bash
python3 land_cover/export_worldcover_idn_mys.py --year 2020
python3 land_cover/export_worldcover_idn_mys.py --year 2021
```

Test region:

```bash
python3 land_cover/export_worldcover_idn_mys.py --year 2020 --test-region
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
./land_cover/download_oilpalm_yop_tiles.sh --remote "rui.song90"
```

## Download WorldCover tiles from Google Drive (rclone)

List remotes:

```bash
rclone listremotes
```

Download tiles (example remote name: `rui.song90`):

```bash
./land_cover/download_worldcover_tiles.sh --remote "rui.song90" --year 2020
./land_cover/download_worldcover_tiles.sh --remote "rui.song90" --year 2021
```

If your rclone config is not in the default location:

```bash
RCLONE_CONFIG=/path/to/rclone.conf ./land_cover/download_worldcover_tiles.sh --remote "rui.song90" --year 2020
```

## Mosaic WorldCover tiles to COG

Outputs go to `land_cover/mosaics/`:

```bash
mkdir -p country_level_data/land_cover/mosaics

gdalbuildvrt country_level_data/land_cover/mosaics/worldcover_2020_idn_mys.vrt \
  country_level_data/land_cover/gee_worldcover_2020_idn_mys/*.tif

gdal_translate country_level_data/land_cover/mosaics/worldcover_2020_idn_mys.vrt \
  country_level_data/land_cover/mosaics/worldcover_2020_idn_mys_cog.tif \
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
  --worldcover country_level_data/land_cover/mosaics/worldcover_2020_idn_mys_cog.tif \
  --oilpalm-dir country_level_data/land_cover/GlobalOilPalm_OP-YoP \
  --out country_level_data/land_cover/mosaics/oilpalm_yop_idn_mys_cog.tif
```
