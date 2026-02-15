#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Clip GlobalOilPalm YoP tiles to Indonesia+Malaysia footprint (from WorldCover COG) and export a COG.

Usage:
  ./land_cover/mosaic_oilpalm_idn_mys.sh [--worldcover <path>] [--oilpalm-dir <dir>] [--out <path>] [--workdir <dir>] [--cutline <path>] [--use-bbox] [--tr <meters>] [--resampling <method>]

Defaults:
  --worldcover ${SCRIPT_DIR}/mosaics/worldcover_2020_idn_mys_cog.tif
  --oilpalm-dir ${SCRIPT_DIR}/GlobalOilPalm_OP-YoP
  --out        ${SCRIPT_DIR}/mosaics/oilpalm_yop_idn_mys_cog.tif
  --workdir    ${SCRIPT_DIR}/mosaics/_yop_work
  --cutline    (optional) precomputed polygon cutline (GPKG/SHP/GeoJSON)
  --use-bbox   use the WorldCover bounding box (less precise than footprint; default)
  --tr         output resolution in meters (default: 30)
  --resampling resampling method (default: near)

Notes:
- Requires GDAL (gdalbuildvrt, gdalwarp, gdalinfo). For footprint cutline, also needs gdal_calc.py + gdal_polygonize.py.
- Cutline is derived from non-zero pixels of the WorldCover COG unless --cutline or --use-bbox is provided.
EOF
}

WORLDCOVER="${SCRIPT_DIR}/mosaics/worldcover_2020_idn_mys_cog.tif"
OILPALM_DIR="${SCRIPT_DIR}/GlobalOilPalm_OP-YoP"
OUT_TIF="${SCRIPT_DIR}/mosaics/oilpalm_yop_idn_mys_cog.tif"
WORKDIR="${SCRIPT_DIR}/mosaics/_yop_work"
CUTLINE=""
USE_BBOX="true"
TR="30"
RESAMPLING="near"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --worldcover)
      WORLDCOVER="$2"
      shift 2
      ;;
    --oilpalm-dir)
      OILPALM_DIR="$2"
      shift 2
      ;;
    --out)
      OUT_TIF="$2"
      shift 2
      ;;
    --workdir)
      WORKDIR="$2"
      shift 2
      ;;
    --cutline)
      CUTLINE="$2"
      shift 2
      ;;
    --use-bbox)
      USE_BBOX="true"
      shift 1
      ;;
    --tr)
      TR="$2"
      shift 2
      ;;
    --resampling)
      RESAMPLING="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

for cmd in gdalbuildvrt gdalwarp gdalinfo; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

if [[ ! -f "$WORLDCOVER" ]]; then
  echo "WorldCover file not found: $WORLDCOVER" >&2
  exit 1
fi

if [[ ! -d "$OILPALM_DIR" ]]; then
  echo "Oil palm directory not found: $OILPALM_DIR" >&2
  exit 1
fi

mkdir -p "$WORKDIR"
mkdir -p "$(dirname "$OUT_TIF")"

VRT="$WORKDIR/oilpalm_yop.vrt"
MASK="$WORKDIR/wc_mask.tif"
AUTO_CUTLINE="$WORKDIR/wc_mask.gpkg"

# Build mosaic VRT from all YoP tiles

gdalbuildvrt "$VRT" "$OILPALM_DIR"/*.tif

if [[ -n "$CUTLINE" ]]; then
  if [[ ! -f "$CUTLINE" ]]; then
    echo "Cutline not found: $CUTLINE" >&2
    exit 1
  fi
elif [[ "$USE_BBOX" == "true" ]]; then
  echo "Using WorldCover bounding box (less precise than footprint)." >&2
else
  if ! command -v gdal_calc.py >/dev/null 2>&1 || ! command -v gdal_polygonize.py >/dev/null 2>&1; then
    echo "Missing gdal_calc.py/gdal_polygonize.py. Install GDAL Python utilities, provide --cutline, or use --use-bbox." >&2
    exit 1
  fi

  # Create a binary mask from WorldCover (1 where data, 0 where nodata)
  gdal_calc.py -A "$WORLDCOVER" --calc="A!=0" --NoDataValue=0 --type=Byte --outfile "$MASK" \
    --co COMPRESS=DEFLATE --co TILED=YES --co BIGTIFF=YES

  # Polygonize mask to vector cutline
  gdal_polygonize.py "$MASK" -f "GPKG" "$AUTO_CUTLINE"
  CUTLINE="$AUTO_CUTLINE"
fi

if [[ "$USE_BBOX" == "true" ]]; then
  read -r MINX MINY < <(gdalinfo "$WORLDCOVER" | awk '/Lower Left/ {gsub(/[()]/, "", $3); gsub(/[(),]/, "", $4); print $3, $4}')
  read -r MAXX MAXY < <(gdalinfo "$WORLDCOVER" | awk '/Upper Right/ {gsub(/[()]/, "", $3); gsub(/[(),]/, "", $4); print $3, $4}')

  gdalwarp \
    -te "$MINX" "$MINY" "$MAXX" "$MAXY" \
    -tr "$TR" "$TR" -tap -r "$RESAMPLING" \
    "$VRT" \
    "$OUT_TIF" \
    -of COG -co COMPRESS=DEFLATE -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS
else
  # Clip YoP mosaic to WorldCover footprint and export as COG
  gdalwarp \
    -cutline "$CUTLINE" \
    -crop_to_cutline \
    -tr "$TR" "$TR" -tap -r "$RESAMPLING" \
    "$VRT" \
    "$OUT_TIF" \
    -of COG -co COMPRESS=DEFLATE -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS
fi

echo "Done: $OUT_TIF"
