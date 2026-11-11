# Google Earth Engine and rclone setup

## Google Earth Engine

1. Register a Cloud project for Earth Engine: https://earthengine.google.com/
   (free for non-commercial and research use; commercial use requires a paid licence).
2. Authenticate once:

   ```bash
   earthengine authenticate
   earthengine set_project <your-cloud-project-id>
   ```

3. Exports are written to the Google Drive of the authenticated account, in folders named
   `gee_<product>_<region>_<year>` (e.g. `gee_worldcover_2021_idn_mys`).
4. Watch progress from the terminal instead of the Code Editor:

   ```bash
   python3 tools/monitor_gee_tasks.py                 # list recent tasks
   python3 tools/monitor_gee_tasks.py --filter agb --wait
   ```

   GEE limits concurrent batch tasks per user; `country_level_data/biomass/submit_agb_exports.sh
   --parallel N` throttles submission.

## rclone (Google Drive → local disk)

1. Install: `conda install -c conda-forge rclone` (included in `environment.yml`) or
   https://rclone.org/install/.
2. Configure a Google Drive remote once (interactive):

   ```bash
   rclone config            # n) New remote → name e.g. "gdrive" → storage "drive" → scope 1 (full)
   rclone listremotes       # should print "gdrive:"
   rclone lsd gdrive:       # should list your Drive folders, incl. gee_* export folders
   ```

3. Pass the remote name to any download script, e.g.

   ```bash
   ./country_level_data/land_cover/download_worldcover_tiles.sh --remote gdrive --year 2021
   ./country_level_data/biomass/download_agb_tiles.sh --remote gdrive --year 2022
   ./country_level_data/fire/sync_and_mosaic_burn_any.sh --remote gdrive --years "2023 2024"
   ```

## Without Google Earth Engine

Stages 2–4 never call GEE. Rasters with the same names, CRS (EPSG:4326) and encodings can be
produced from other providers (Copernicus Data Space Ecosystem for WorldCover, ESA CCI Open
Data Portal for AGB, NASA LP DAAC for MCD64A1) and placed in `country_level_data/*/mosaics/`.
