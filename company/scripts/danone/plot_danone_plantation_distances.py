#!/usr/bin/env python3
import argparse
import math
import sys
from pathlib import Path

import matplotlib
import numpy as np


matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common.uml_tools import haversine_km, parse_decimal


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_INPUT_DIR = COMPANY_DIR / "results" / "danone" / "uml"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "histograms"
FIGSIZE = (10, 6)


def load_distances(csv_path: Path, max_distance_km: float | None):
    import csv

    distances = []
    skipped = 0
    removed = 0
    with csv_path.open(newline="", encoding="latin-1") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            mill_lat = parse_decimal(row.get("Latitude", ""))
            mill_lon = parse_decimal(row.get("Longitude", ""))
            plantation_lat = parse_decimal(row.get("Plantation Latitude", ""))
            plantation_lon = parse_decimal(row.get("Plantation Longitude", ""))
            dist = haversine_km(plantation_lat, plantation_lon, mill_lat, mill_lon)
            if dist is None:
                skipped += 1
                continue
            if max_distance_km is not None and dist > max_distance_km:
                removed += 1
                continue
            distances.append(dist)
    return distances, skipped, removed


def _kde_gaussian(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    n = values.size
    if n < 2:
        return np.zeros_like(grid)
    std = values.std(ddof=1)
    iqr = np.subtract(*np.percentile(values, [75, 25]))
    sigma = std if iqr == 0 else min(std, iqr / 1.349)
    bandwidth = 0.9 * sigma * n ** (-1 / 5)
    if bandwidth <= 0:
        bandwidth = 1.0
    diff = (grid[:, None] - values[None, :]) / bandwidth
    kernel = np.exp(-0.5 * diff**2)
    return kernel.sum(axis=1) / (n * bandwidth * math.sqrt(2 * math.pi))


def plot_histogram(distances, output_path: Path, *, grid: np.ndarray | None = None, y_max: float | None = None):
    values = np.array(distances, dtype=float)
    if grid is None:
        xmin = max(0.0, float(values.min()))
        xmax = float(values.max())
        grid = np.linspace(xmin, xmax, 512)
    density = _kde_gaussian(values, grid)

    plt.style.use("seaborn-v0_8-white")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.fill_between(grid, density, color="#8fbce6", alpha=0.6, linewidth=0)
    ax.plot(grid, density, color="#1f4b7a", linewidth=2.5)

    mean = values.mean()
    median = float(np.median(values))
    ax.axvline(mean, color="#1f4b7a", linestyle="--", linewidth=1.5, label=f"Mean: {mean:.1f} km")
    ax.axvline(median, color="#4b5563", linestyle=":", linewidth=1.5, label=f"Median: {median:.1f} km")

    ax.set_xlabel("Distance (km)", fontsize=16)
    ax.set_ylabel("Density", fontsize=16)
    ax.legend(frameon=False, loc="upper right", fontsize=14)
    ax.grid(False)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=y_max)
    ax.tick_params(axis="both", which="major", labelsize=14, length=6, width=1)
    ax.tick_params(axis="both", which="minor", labelsize=12, length=3, width=0.8)
    ax.minorticks_on()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)


def main():
    parser = argparse.ArgumentParser(description="Plot Danone plantation-to-mill distance charts.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Directory containing matched_plantations CSVs")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to save histogram PNGs")
    parser.add_argument("--max-distance-km", type=float, default=200, help="Drop rows beyond this distance")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_paths = sorted(input_dir.glob("matched_plantations*.csv"))
    if not csv_paths:
        raise SystemExit(f"No matched_plantations CSVs found in {input_dir}")

    per_file = []
    global_max = 0.0
    for csv_path in csv_paths:
        distances, skipped, removed = load_distances(csv_path, args.max_distance_km)
        if distances:
            global_max = max(global_max, max(distances))
        per_file.append((csv_path, distances, skipped, removed))
    if global_max <= 0:
        raise SystemExit("No valid distances found. Check plantation coordinate columns.")

    grid = np.linspace(0.0, global_max, 512)
    y_max = 0.0
    for _, distances, _, _ in per_file:
        if not distances:
            continue
        density = _kde_gaussian(np.array(distances, dtype=float), grid)
        y_max = max(y_max, float(density.max()) if density.size else 0.0)
    if y_max <= 0:
        raise SystemExit("Unable to compute density range.")

    for csv_path, distances, skipped, removed in per_file:
        if not distances:
            print(f"{csv_path.name}: no valid distances, skipped")
            continue
        out_path = output_dir / f"{csv_path.stem}_hist.png"
        plot_histogram(distances, out_path, grid=grid, y_max=y_max)
        print(f"{csv_path.name}: rows={len(distances)}, skipped={skipped}, removed={removed}")
        print(f"Histogram saved: {out_path}")


if __name__ == "__main__":
    main()
