#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Mosaic ESA CCI AGB tiles into a COG.

Usage:
  ./biomass/mosaic_agb_tiles.sh --year <2015-2022> [--input-dir <dir>] [--out-dir <dir>]

Examples:
  ./biomass/mosaic_agb_tiles.sh --year 2022
  ./biomass/mosaic_agb_tiles.sh --year 2022 --input-dir /path/to/tiles --out-dir /path/to/mosaics
EOF
}

YEAR=""
INPUT_DIR=""
OUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --year)
      YEAR="$2"
      shift 2
      ;;
    --input-dir)
      INPUT_DIR="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
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

if [[ -z "$YEAR" ]]; then
  echo "--year is required." >&2
  usage
  exit 1
fi

if [[ "$YEAR" -lt 2015 || "$YEAR" -gt 2022 ]]; then
  echo "--year must be between 2015 and 2022." >&2
  exit 1
fi

if [[ -z "$INPUT_DIR" ]]; then
  INPUT_DIR="${SCRIPT_DIR}/gee_agb_${YEAR}_idn_mys"
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="${SCRIPT_DIR}/mosaics"
fi

mkdir -p "$OUT_DIR"

VRT="${OUT_DIR}/agb_${YEAR}_idn_mys.vrt"
COG="${OUT_DIR}/agb_${YEAR}_idn_mys_cog.tif"

echo "Building VRT: $VRT"
gdalbuildvrt "$VRT" "${INPUT_DIR}"/*.tif

echo "Translating to COG: $COG"
gdal_translate "$VRT" "$COG" -of COG -co COMPRESS=DEFLATE -co BIGTIFF=YES

echo "Done."
