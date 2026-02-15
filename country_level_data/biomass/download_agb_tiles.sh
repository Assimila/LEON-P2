#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Download ESA CCI AGB tiles from Google Drive using rclone.

Usage:
  ./biomass/download_agb_tiles.sh --remote <rclone_remote> --year <2015-2022> [--drive-path <path>]

Examples:
  ./biomass/download_agb_tiles.sh --remote gdrive --year 2022
  ./biomass/download_agb_tiles.sh --remote gdrive --year 2022 --drive-path "My Drive/gee_agb_2022_idn_mys"

Notes:
- rclone must be installed and configured with a Google Drive remote.
- If --drive-path is not provided, it defaults to the folder name in My Drive.
EOF
}

REMOTE=""
YEAR=""
DRIVE_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      REMOTE="$2"
      shift 2
      ;;
    --year)
      YEAR="$2"
      shift 2
      ;;
    --drive-path)
      DRIVE_PATH="$2"
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

if [[ -z "$REMOTE" || -z "$YEAR" ]]; then
  echo "--remote and --year are required." >&2
  usage
  exit 1
fi

if [[ "$YEAR" -lt 2015 || "$YEAR" -gt 2022 ]]; then
  echo "--year must be between 2015 and 2022." >&2
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone not found. Install it and run 'rclone config' first." >&2
  exit 1
fi

FOLDER_NAME="gee_agb_${YEAR}_idn_mys"
if [[ -z "$DRIVE_PATH" ]]; then
  DRIVE_PATH="$FOLDER_NAME"
fi

DEST_DIR="${SCRIPT_DIR}/$FOLDER_NAME"
mkdir -p "$DEST_DIR"

SRC="${REMOTE}:${DRIVE_PATH}"

echo "Downloading from: $SRC"
echo "Destination: $DEST_DIR"

rclone copy "$SRC" "$DEST_DIR" --progress --transfers 4 --checkers 8

echo "Done."
