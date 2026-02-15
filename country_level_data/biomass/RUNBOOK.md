# Biomass Runbook

Practical commands for exporting, downloading, and mosaicking AGB data.

## AGB export (GEE)

Submit all years (2015-2022) in parallel:

```bash
./biomass/submit_agb_exports.sh --parallel 4 --scale 100 --nan-zeros
```

Single year test region (50x50 km):

```bash
python3 biomass/export_agb_idn_mys.py --year 2022 --test-region --test-size-km 50 --scale 100 --nan-zeros
```

## Download AGB tiles from Google Drive (rclone)

List remotes:

```bash
rclone listremotes
```

Download tiles (example remote name: `rui.song90`):

```bash
./biomass/download_agb_tiles.sh --remote "rui.song90" --year 2022
```

## Mosaic AGB tiles to COG

Outputs go to `biomass/mosaics/`:

```bash
./biomass/mosaic_agb_tiles.sh --year 2022
```

## Mill-level AGB multi-panel plots (2015-2022)

Example for one mill (50 km radius):

```bash
conda run -n geospatial python country_level_data/biomass/plot_mill_agb_panels.py \
  --mill-id PO1000000058 \
  --company CARGILL \
  --mill-name HINDOLI \
  --lat -2.612778 --lon 104.128242 \
  --radius-km 50
```

Note: AGB is masked to the circular supply shed; values outside the chosen radius are removed.
