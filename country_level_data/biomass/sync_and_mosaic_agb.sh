#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Sync ESA CCI AGB tiles from Google Drive and mosaic per year.

Usage:
  ./biomass/sync_and_mosaic_agb.sh --remote <rclone_remote> [--years "2015 2016 ... 2022"]
                                  [--drive-root <path>] [--input-root <dir>] [--out-dir <dir>]

Examples:
  ./biomass/sync_and_mosaic_agb.sh --remote "rui.song90"
  ./biomass/sync_and_mosaic_agb.sh --remote "rui.song90" --years "2020 2021 2022"
  ./biomass/sync_and_mosaic_agb.sh --remote "rui.song90" --drive-root "My Drive"
EOF
}

REMOTE=""
YEARS_STR=""
DRIVE_ROOT=""
INPUT_ROOT=""
OUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      REMOTE="$2"
      shift 2
      ;;
    --years)
      YEARS_STR="$2"
      shift 2
      ;;
    --drive-root)
      DRIVE_ROOT="$2"
      shift 2
      ;;
    --input-root)
      INPUT_ROOT="$2"
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

if [[ -z "$REMOTE" ]]; then
  echo "--remote is required." >&2
  usage
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone not found. Install it and run 'rclone config' first." >&2
  exit 1
fi

if [[ -z "$YEARS_STR" ]]; then
  YEARS_STR="$(seq 2015 2022 | tr '\n' ' ')"
fi
IFS=$' \t\n' read -r -a YEARS <<<"$YEARS_STR"

if [[ -z "$DRIVE_ROOT" ]]; then
  DRIVE_ROOT=""
fi

if [[ -z "$INPUT_ROOT" ]]; then
  INPUT_ROOT="${SCRIPT_DIR}"
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="${SCRIPT_DIR}/mosaics"
fi

mkdir -p "$OUT_DIR"

for YEAR in "${YEARS[@]}"; do
  if [[ "$YEAR" -lt 2015 || "$YEAR" -gt 2022 ]]; then
    echo "Skipping invalid year: $YEAR" >&2
    continue
  fi

  FOLDER_NAME="gee_agb_${YEAR}_idn_mys"
  if [[ -z "$DRIVE_ROOT" ]]; then
    DRIVE_PATH="$FOLDER_NAME"
  else
    DRIVE_PATH="${DRIVE_ROOT}/${FOLDER_NAME}"
  fi

  DEST_DIR="${INPUT_ROOT}/${FOLDER_NAME}"
  mkdir -p "$DEST_DIR"

  echo "Syncing year $YEAR from ${REMOTE}:${DRIVE_PATH}"
  rclone sync "${REMOTE}:${DRIVE_PATH}" "$DEST_DIR" --progress --transfers 4 --checkers 8

  echo "Mosaicking year $YEAR"
  "${SCRIPT_DIR}/mosaic_agb_tiles.sh" --year "$YEAR" --input-dir "$DEST_DIR" --out-dir "$OUT_DIR"
done

echo "All years synced and mosaicked."
