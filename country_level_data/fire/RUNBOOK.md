# Fire Runbook (MODIS MCD64A1, 2001–2024)

Practical commands for exporting, downloading and mosaicking the annual
"burned at least once" fire masks for Indonesia and Malaysia, and for producing
the fire-frequency figure. Run commands from `country_level_data/`.

Product: MODIS MCD64A1 v6.1 `BurnDate` (~500 m, monthly). Each annual output is a
single-band Byte raster: `1` = any month burned in the year, `0` = not burned.

## 1. Export annual burn masks (Google Earth Engine)

Prerequisite: `earthengine authenticate` and a GEE Cloud project (see
`docs/gee_and_rclone_setup.md`).

Single year, small test region first (~3 x 3 km):

```bash
python3 fire/export_modis_burn_any_idn_mys.py --year 2024 --test-region
```

Single full year:

```bash
python3 fire/export_modis_burn_any_idn_mys.py --year 2024
```

Batch of years (one GEE task per year, exported to Google Drive folders named
`gee_mcd64a1_burn_any_idn_mys_<YEAR>`):

```bash
python3 fire/export_modis_burn_any_idn_mys_years.py --start-year 2001 --end-year 2024
```

Monitor the tasks without opening the Code Editor:

```bash
python3 ../tools/monitor_gee_tasks.py --filter mcd64a1 --wait
```

## 2. Download tiles and mosaic to COG (rclone + GDAL)

Download from Google Drive and mosaic in one step (remote name from `rclone listremotes`):

```bash
./fire/sync_and_mosaic_burn_any.sh --remote "<your_remote>" --years "2023 2024"
```

Mosaic only (tiles already downloaded):

```bash
./fire/sync_and_mosaic_burn_any.sh --years "2001 2002 2003" --mosaic-only
# or a single year
./fire/mosaic_burn_any_tiles.sh --year 2024
```

Outputs: `fire/mosaics/mcd64a1_burn_any_<YEAR>_idn_mys_cog.tif`
(~70–180 KB per year; ~3 MB for 2001–2024).

## 3. Visualise

Annual small-multiples:

```bash
python3 fire/visualize_burn_any_annual.py --start-year 2001 --end-year 2024
```

Fire-frequency map (share of years with a detected burn):

```bash
python3 fire/plot_fire_frequency.py --start-year 2001 --end-year 2024 --hide-zero
```

## 4. Supply-shed fire statistics

Per-mill fire incidence for 25 km and 50 km supply sheds is produced by
`supply_shed_indicators/fire/` (see its README).

## Known limitations

- MCD64A1 detection probability rises with fire size and contiguity; small or
  low-intensity fires, and fires under persistent smoke/cloud, can be missed.
- The annual binary mask does not retain sub-annual timing. Use the
  `export_modis_burn_date_*` scripts if burn day-of-year is needed.
- The product is retrospective, not a near-real-time alert. Early-warning use
  (AG-UR-07) would need VIIRS active-fire or GLAD/RADD alerts.
