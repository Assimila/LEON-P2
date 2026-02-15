#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Bias-correct WorldCover by overriding pixels to class 11 where oil palm YoP <= 2021.

Usage:
  ./land_cover/bias_correct_worldcover_with_oilpalm.sh [--worldcover <path>] [--oilpalm <path>] [--out <path>] [--workdir <dir>] [--year <YYYY>]

Defaults:
  --worldcover ${SCRIPT_DIR}/mosaics/worldcover_2021_idn_mys_cog.tif
  --oilpalm   ${SCRIPT_DIR}/mosaics/oilpalm_yop_2021_idn_mys_cog.tif
  --out       ${SCRIPT_DIR}/mosaics/worldcover_2021_idn_mys_bias_oilpalm_cog.tif
  --workdir   ${SCRIPT_DIR}/mosaics/_wc_bias_work
  --year      2021

Notes:
- Requires GDAL (gdalwarp, gdal_calc.py, gdal_translate, gdalinfo).
- Oil palm YoP is resampled to the WorldCover grid using nearest neighbor.
EOF
}

WORLDCOVER="${SCRIPT_DIR}/mosaics/worldcover_2021_idn_mys_cog.tif"
OILPALM="${SCRIPT_DIR}/mosaics/oilpalm_yop_2021_idn_mys_cog.tif"
OUT_TIF="${SCRIPT_DIR}/mosaics/worldcover_2021_idn_mys_bias_oilpalm_cog.tif"
WORKDIR="${SCRIPT_DIR}/mosaics/_wc_bias_work"
YEAR="2021"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --worldcover)
      WORLDCOVER="$2"
      shift 2
      ;;
    --oilpalm)
      OILPALM="$2"
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
    --year)
      YEAR="$2"
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

for cmd in gdalwarp gdal_calc.py gdal_translate gdalinfo; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

if [[ ! -f "$WORLDCOVER" ]]; then
  echo "WorldCover file not found: $WORLDCOVER" >&2
  exit 1
fi

if [[ ! -f "$OILPALM" ]]; then
  echo "Oil palm file not found: $OILPALM" >&2
  exit 1
fi

mkdir -p "$WORKDIR"
mkdir -p "$(dirname "$OUT_TIF")"

OILPALM_ALIGNED="$WORKDIR/oilpalm_yop_2021_aligned.tif"
OUT_TMP="$WORKDIR/worldcover_2021_bias_oilpalm.tif"

# Clean previous intermediates to avoid GDAL "exists" errors.
rm -f "$OILPALM_ALIGNED" "$OUT_TMP" "$OUT_TIF"

# Align oil palm YoP to WorldCover grid (extent + pixel size)
UL_LINE="$(gdalinfo "$WORLDCOVER" | awk -F'[(),]' '/Upper Left/ {gsub(/ /, "", $2); gsub(/ /, "", $3); print $2" "$3; exit}')"
LR_LINE="$(gdalinfo "$WORLDCOVER" | awk -F'[(),]' '/Lower Right/ {gsub(/ /, "", $2); gsub(/ /, "", $3); print $2" "$3; exit}')"
read -r MINX MAXY <<< "$UL_LINE"
read -r MAXX MINY <<< "$LR_LINE"

SIZE_LINE="$(gdalinfo "$WORLDCOVER" | awk -F'[ ,]+' '/Size is/ {print $3" "$4; exit}')"
read -r SIZE_X SIZE_Y <<< "$SIZE_LINE"

SRS_LINE="$(gdalinfo "$WORLDCOVER" -proj4 | tail -n 1)"
if [[ -z "$SRS_LINE" || "$SRS_LINE" != +proj* ]]; then
  SRS_LINE=""
fi

gdalwarp \
  -overwrite \
  ${SRS_LINE:+-t_srs "$SRS_LINE"} \
  -te "$MINX" "$MINY" "$MAXX" "$MAXY" \
  -ts "$SIZE_X" "$SIZE_Y" -r near \
  -srcnodata 0 -dstnodata 0 \
  "$OILPALM" \
  "$OILPALM_ALIGNED" \
  -co COMPRESS=DEFLATE -co TILED=YES -co BIGTIFF=YES

# Bias-correct: set WorldCover class to 11 where oil palm year <= 2021
gdal_calc.py \
  -A "$WORLDCOVER" \
  -B "$OILPALM_ALIGNED" \
  --calc="where((B>0)*(floor(B)<=${YEAR}), 11, A)" \
  --type=Byte \
  --NoDataValue=0 \
  --outfile "$OUT_TMP" \
  --co COMPRESS=DEFLATE --co TILED=YES --co BIGTIFF=YES

# Convert to COG
gdal_translate \
  "$OUT_TMP" \
  "$OUT_TIF" \
  -of COG -co COMPRESS=DEFLATE -co LEVEL=9 -co PREDICTOR=2 -co BIGTIFF=YES

echo "Done: $OUT_TIF"
