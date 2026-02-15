#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Mosaic GlobalOilPalm YoP tiles and mask to the WorldCover footprint (IDN+MYS).

Usage:
  ./land_cover/mosaic_oilpalm_idn_mys_mask.sh [--worldcover <path>] [--oilpalm-dir <dir>] [--out <path>] [--workdir <dir>] [--tr <meters>]

Defaults:
  --worldcover ${SCRIPT_DIR}/mosaics/worldcover_2020_idn_mys_cog.tif
  --oilpalm-dir ${SCRIPT_DIR}/GlobalOilPalm_OP-YoP
  --out        ${SCRIPT_DIR}/mosaics/oilpalm_yop_idn_mys_30m_cog.tif
  --workdir    ${SCRIPT_DIR}/mosaics/_yop_mask_work
  --tr         output resolution in source units (default: auto from YoP tiles)

Notes:
- Requires GDAL (gdalbuildvrt, gdalwarp, gdal_calc.py, gdal_translate).
- This aligns WorldCover to the YoP 30m grid and masks YoP outside the footprint.
EOF
}

WORLDCOVER="${SCRIPT_DIR}/mosaics/worldcover_2020_idn_mys_cog.tif"
OILPALM_DIR="${SCRIPT_DIR}/GlobalOilPalm_OP-YoP"
OUT_TIF="${SCRIPT_DIR}/mosaics/oilpalm_yop_idn_mys_30m_cog.tif"
WORKDIR="${SCRIPT_DIR}/mosaics/_yop_mask_work"
TR=""

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
    --tr)
      TR="$2"
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

for cmd in gdalbuildvrt gdalwarp gdal_calc.py gdal_translate; do
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
WC_30M="$WORKDIR/worldcover_idn_mys_30m.tif"
MASK="$WORKDIR/worldcover_idn_mys_mask_30m.tif"
YOPOUT="$WORKDIR/oilpalm_yop_idn_mys_30m.tif"

# Clean previous intermediates to avoid GDAL "exists" errors.
rm -f "$WC_30M" "$MASK" "$YOPOUT"

# 1) Build YoP VRT
gdalbuildvrt "$VRT" "$OILPALM_DIR"/*.tif

# 2) Align WorldCover to YoP grid/extent
# Derive pixel size and extent from YoP VRT (works without gdalinfo -json).
PIXEL_SIZE_LINE="$(gdalinfo "$VRT" | awk -F'[(),]' '/Pixel Size/ {gsub(/ /, "", $2); gsub(/ /, "", $3); print $2","$3; exit}')"
PIX_X="${PIXEL_SIZE_LINE%,*}"
PIX_Y="${PIXEL_SIZE_LINE#*,}"
PIX_X="${PIX_X#-}"
PIX_Y="${PIX_Y#-}"

RASTER_SIZE_LINE="$(gdalinfo "$VRT" | awk -F'[ ,]+' '/Size is/ {print $3" "$4; exit}')"
read -r RASTER_X RASTER_Y <<< "$RASTER_SIZE_LINE"

UL_LINE="$(gdalinfo "$VRT" | awk -F'[(),]' '/Upper Left/ {gsub(/ /, "", $2); gsub(/ /, "", $3); print $2" "$3; exit}')"
LR_LINE="$(gdalinfo "$VRT" | awk -F'[(),]' '/Lower Right/ {gsub(/ /, "", $2); gsub(/ /, "", $3); print $2" "$3; exit}')"

read -r MINX MAXY <<< "$UL_LINE"
read -r MAXX MINY <<< "$LR_LINE"

if [[ -z "$TR" ]]; then
  TR="$PIX_X"
fi
TR="${TR#-}"

SRS="$(gdalinfo "$VRT" -proj4 | tail -n 1)"
if [[ -z "$SRS" || "$SRS" != +proj* ]]; then
  SRS=""
fi

gdalwarp \
  -overwrite \
  ${SRS:+-t_srs "$SRS"} \
  -te "$MINX" "$MINY" "$MAXX" "$MAXY" \
  -ts "$RASTER_X" "$RASTER_Y" -r near \
  "$WORLDCOVER" \
  "$WC_30M" \
  -co COMPRESS=DEFLATE -co TILED=YES -co BIGTIFF=YES

# 3) Build mask from WorldCover (1 inside, 0 outside)
gdal_calc.py \
  -A "$WC_30M" \
  --calc="A>0" --type=Byte --NoDataValue=0 \
  --outfile "$MASK" \
  --co COMPRESS=DEFLATE --co TILED=YES --co BIGTIFF=YES

# 4) Apply mask to YoP
gdal_calc.py \
  -A "$VRT" \
  -B "$MASK" \
  --calc="A*(B==1)" --NoDataValue=0 \
  --outfile "$YOPOUT" \
  --co COMPRESS=DEFLATE --co TILED=YES --co BIGTIFF=YES

# 5) Convert to COG
gdal_translate \
  "$YOPOUT" \
  "$OUT_TIF" \
  -of COG -co COMPRESS=DEFLATE

echo "Done: $OUT_TIF"
