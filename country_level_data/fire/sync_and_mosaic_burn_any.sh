#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Sync MODIS MCD64A1 annual burn-any tiles from Google Drive and mosaic per year.

Usage:
  ./fire/sync_and_mosaic_burn_any.sh --remote <rclone_remote> [--years "2020 2021 ..."]
                                     [--drive-root <path>] [--input-root <dir>] [--out-dir <dir>]
  ./fire/sync_and_mosaic_burn_any.sh --years "2020 2021 ..." [--input-root <dir>] [--out-dir <dir>] --mosaic-only

Examples:
  ./fire/sync_and_mosaic_burn_any.sh --remote "rui.song90" --years "2023 2024"
  ./fire/sync_and_mosaic_burn_any.sh --remote "rui.song90" --drive-root "My Drive"
  ./fire/sync_and_mosaic_burn_any.sh --years "2001 2002 2003" --mosaic-only
EOF
}

REMOTE=""
YEARS_STR=""
DRIVE_ROOT=""
INPUT_ROOT=""
OUT_DIR=""
MOSAIC_ONLY="false"

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
    --mosaic-only)
      MOSAIC_ONLY="true"
      shift 1
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
  if [[ "$MOSAIC_ONLY" != "true" ]]; then
    echo "--remote is required unless --mosaic-only is set." >&2
    usage
    exit 1
  fi
fi

if [[ "$MOSAIC_ONLY" != "true" ]]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone not found. Install it and run 'rclone config' first." >&2
    exit 1
  fi
fi

if [[ -z "$YEARS_STR" ]]; then
  YEARS_STR="$(seq 2015 2025 | tr '\n' ' ')"
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
  FOLDER_NAME="gee_mcd64a1_burn_any_idn_mys_${YEAR}"
  if [[ -z "$DRIVE_ROOT" ]]; then
    DRIVE_PATH="$FOLDER_NAME"
  else
    DRIVE_PATH="${DRIVE_ROOT}/${FOLDER_NAME}"
  fi

  DEST_DIR="${INPUT_ROOT}/${FOLDER_NAME}"
  mkdir -p "$DEST_DIR"

  if [[ "$MOSAIC_ONLY" != "true" ]]; then
    echo "Syncing year $YEAR from ${REMOTE}:${DRIVE_PATH}"
    rclone sync "${REMOTE}:${DRIVE_PATH}" "$DEST_DIR" --progress --transfers 4 --checkers 8
  else
    if [[ ! -d "$DEST_DIR" ]]; then
      echo "Tiles directory not found: $DEST_DIR" >&2
      exit 1
    fi
  fi

  echo "Mosaicking year $YEAR"
  "${SCRIPT_DIR}/mosaic_burn_any_tiles.sh" --year "$YEAR" --input-dir "$DEST_DIR" --out-dir "$OUT_DIR"
done

echo "All years synced and mosaicked."
