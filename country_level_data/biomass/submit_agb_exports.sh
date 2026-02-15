#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Submit ESA CCI AGB exports to Google Drive in parallel.

Usage:
  ./biomass/submit_agb_exports.sh [--years "2015 2016 ... 2022"] [--parallel N]
                                 [--scale METERS] [--nan-zeros]
                                 [--test-region] [--test-size-km KM]

Examples:
  ./biomass/submit_agb_exports.sh
  ./biomass/submit_agb_exports.sh --parallel 4 --scale 100 --nan-zeros
  ./biomass/submit_agb_exports.sh --years "2019 2020 2021 2022"
EOF
}

YEARS_STR=""
PARALLEL=4
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --years)
      YEARS_STR="$2"
      shift 2
      ;;
    --parallel)
      PARALLEL="$2"
      shift 2
      ;;
    --scale)
      EXTRA_ARGS+=(--scale "$2")
      shift 2
      ;;
    --nan-zeros)
      EXTRA_ARGS+=(--nan-zeros)
      shift 1
      ;;
    --test-region)
      EXTRA_ARGS+=(--test-region)
      shift 1
      ;;
    --test-size-km)
      EXTRA_ARGS+=(--test-size-km "$2")
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

if [[ -z "$YEARS_STR" ]]; then
  YEARS_STR="$(seq 2015 2022 | tr '\n' ' ')"
fi

IFS=$' \t\n' read -r -a YEARS <<<"$YEARS_STR"

if [[ "$PARALLEL" -lt 1 ]]; then
  echo "--parallel must be >= 1" >&2
  exit 1
fi

PIDS=()

for YEAR in "${YEARS[@]}"; do
  echo "Submitting export for year $YEAR"
  python3 biomass/export_agb_idn_mys.py --year "$YEAR" "${EXTRA_ARGS[@]}" &
  PIDS+=("$!")

  # Throttle: wait for the oldest job when hitting the limit.
  if [[ "${#PIDS[@]}" -ge "$PARALLEL" ]]; then
    PID="${PIDS[0]}"
    wait "$PID"
    PIDS=("${PIDS[@]:1}")
  fi
done

# Wait for remaining jobs.
for PID in "${PIDS[@]}"; do
  wait "$PID"
done

echo "All exports submitted."
