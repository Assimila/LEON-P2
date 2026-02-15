#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Download ESA WorldCover tiles from Google Drive using rclone.

Usage:
  ./land_cover/download_worldcover_tiles.sh --remote <rclone_remote> --year <2020|2021> [--drive-path <path>]

Examples:
  ./land_cover/download_worldcover_tiles.sh --remote gdrive --year 2020
  ./land_cover/download_worldcover_tiles.sh --remote gdrive --year 2021 --drive-path "My Drive/gee_worldcover_2021_idn_mys"

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

if [[ "$YEAR" != "2020" && "$YEAR" != "2021" ]]; then
  echo "--year must be 2020 or 2021." >&2
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone not found. Install it and run 'rclone config' first." >&2
  exit 1
fi

FOLDER_NAME="gee_worldcover_${YEAR}_idn_mys"
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
