#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Download GlobalOilPalm YoP tiles from Google Drive using rclone.

Usage:
  ./land_cover/download_oilpalm_yop_tiles.sh --remote <rclone_remote> [--drive-path <path>]

Defaults:
  --drive-path gee_globaloilpalm_yop_2021_idn_mys

Notes:
- rclone must be installed and configured with a Google Drive remote.
EOF
}

REMOTE=""
DRIVE_PATH="gee_globaloilpalm_yop_2021_idn_mys"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      REMOTE="$2"
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

if [[ -z "$REMOTE" ]]; then
  echo "--remote is required." >&2
  usage
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone not found. Install it and run 'rclone config' first." >&2
  exit 1
fi

DEST_DIR="${SCRIPT_DIR}/gee_globaloilpalm_yop_2021_idn_mys"
mkdir -p "$DEST_DIR"

SRC="${REMOTE}:${DRIVE_PATH}"

echo "Downloading from: $SRC"
echo "Destination: $DEST_DIR"

rclone copy "$SRC" "$DEST_DIR" --progress --transfers 4 --checkers 8

echo "Done."
