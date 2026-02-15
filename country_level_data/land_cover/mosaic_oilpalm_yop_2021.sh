#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Mosaic GlobalOilPalm YoP 2021 tiles to a single COG.

Usage:
  ./land_cover/mosaic_oilpalm_yop_2021.sh [--input-dir <dir>] [--out <path>]

Defaults:
  --input-dir ${SCRIPT_DIR}/gee_globaloilpalm_yop_2021_idn_mys
  --out       ${SCRIPT_DIR}/mosaics/oilpalm_yop_2021_idn_mys_cog.tif
EOF
}

INPUT_DIR="${SCRIPT_DIR}/gee_globaloilpalm_yop_2021_idn_mys"
OUT_TIF="${SCRIPT_DIR}/mosaics/oilpalm_yop_2021_idn_mys_cog.tif"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input-dir)
      INPUT_DIR="$2"
      shift 2
      ;;
    --out)
      OUT_TIF="$2"
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

for cmd in gdalbuildvrt gdal_translate; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "Input directory not found: $INPUT_DIR" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_TIF")"

VRT="${OUT_TIF%.tif}.vrt"

gdalbuildvrt "$VRT" "$INPUT_DIR"/*.tif

gdal_translate \
  "$VRT" \
  "$OUT_TIF" \
  -of COG -co COMPRESS=DEFLATE -co BIGTIFF=YES

echo "Done: $OUT_TIF"
