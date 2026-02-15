#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Mosaic MODIS MCD64A1 annual burn-any tiles into a COG.

Usage:
  ./fire/mosaic_burn_any_tiles.sh --year <YYYY> [--input-dir <dir>] [--out-dir <dir>]

Examples:
  ./fire/mosaic_burn_any_tiles.sh --year 2024
  ./fire/mosaic_burn_any_tiles.sh --year 2024 --input-dir /path/to/tiles --out-dir /path/to/mosaics
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

if [[ -z "$INPUT_DIR" ]]; then
  INPUT_DIR="${SCRIPT_DIR}/gee_mcd64a1_burn_any_idn_mys_${YEAR}"
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="${SCRIPT_DIR}/mosaics"
fi

for cmd in gdalbuildvrt gdal_translate; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

mkdir -p "$OUT_DIR"

VRT="${OUT_DIR}/mcd64a1_burn_any_${YEAR}_idn_mys.vrt"
COG="${OUT_DIR}/mcd64a1_burn_any_${YEAR}_idn_mys_cog.tif"

echo "Building VRT: $VRT"
gdalbuildvrt "$VRT" "${INPUT_DIR}"/*.tif

echo "Translating to COG: $COG"
gdal_translate "$VRT" "$COG" -of COG -co COMPRESS=DEFLATE -co BIGTIFF=YES

echo "Done."
