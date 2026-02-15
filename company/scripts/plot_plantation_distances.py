#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib
import numpy as np


matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIGSIZE = (10, 6)


def parse_decimal(value: str):
    if value is None:
        return None
    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_distances(csv_path: Path, max_distance_km: float | None):
    distances = []
    skipped = 0
    removed = 0
    with csv_path.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
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
    density = kernel.sum(axis=1) / (n * bandwidth * math.sqrt(2 * math.pi))
    return density


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

    label_size = 16
    tick_size = 14
    legend_size = 14
    ax.set_xlabel("Distance (km)", fontsize=label_size)
    ax.set_ylabel("Density", fontsize=label_size)
    ax.legend(frameon=False, loc="upper right", fontsize=legend_size)
    ax.grid(False)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=y_max)
    ax.tick_params(axis="both", which="major", labelsize=tick_size, length=6, width=1)
    ax.tick_params(axis="both", which="minor", labelsize=tick_size - 2, length=3, width=0.8)
    ax.minorticks_on()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)


def main():
    parser = argparse.ArgumentParser(
        description="Plot histogram of plantation-to-mill distances from UML/matched_plantations.csv"
    )
    parser.add_argument(
        "--input",
        default="UML",
        help="CSV file or directory containing matched_plantations*.csv files",
    )
    parser.add_argument(
        "--output",
        default="UML/plantation_distance_histogram.png",
        help="Path to save histogram PNG",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="If set and input is a directory, save one histogram per CSV in this directory",
    )
    parser.add_argument(
        "--max-distance-km",
        type=float,
        default=200,
        help="Drop rows with distance greater than this threshold",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if input_path.is_dir():
        csv_paths = sorted(input_path.glob("matched_plantations*.csv"))
        if not csv_paths:
            raise SystemExit(f"No matched_plantations CSVs found in {input_path}")
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            per_file = []
            global_max = 0.0
            for csv_path in csv_paths:
                distances, skipped, removed = load_distances(csv_path, args.max_distance_km)
                if distances:
                    max_val = max(distances)
                    if max_val > global_max:
                        global_max = max_val
                per_file.append((csv_path, distances, skipped, removed))
            if global_max <= 0:
                raise SystemExit("No valid distances found. Check latitude/longitude columns.")
            grid = np.linspace(0.0, global_max, 512)
            y_max = 0.0
            for _, distances, _, _ in per_file:
                if not distances:
                    continue
                density = _kde_gaussian(np.array(distances, dtype=float), grid)
                peak = float(density.max()) if density.size else 0.0
                if peak > y_max:
                    y_max = peak
            if y_max <= 0:
                raise SystemExit("Unable to compute density range.")

            for csv_path in csv_paths:
                distances, skipped, removed = load_distances(csv_path, args.max_distance_km)
                if not distances:
                    print(f"{csv_path.name}: no valid distances, skipped")
                    continue
                out_path = output_dir / f"{csv_path.stem}_hist.png"
                plot_histogram(distances, out_path, grid=grid, y_max=y_max)
                print(f"{csv_path.name}: rows={len(distances)}, skipped={skipped}, removed={removed}")
                print(f"Histogram saved: {out_path}")
        else:
            distances = []
            skipped = 0
            removed = 0
            for csv_path in csv_paths:
                d, s, r = load_distances(csv_path, args.max_distance_km)
                distances.extend(d)
                skipped += s
                removed += r
            if not distances:
                raise SystemExit("No valid distances found. Check latitude/longitude columns.")
            plot_histogram(distances, output_path)
            print(f"Rows with distance: {len(distances)}")
            print(f"Rows skipped: {skipped}")
            print(f"Rows removed (> {args.max_distance_km} km): {removed}")
            print(f"Histogram saved: {output_path}")
    else:
        distances, skipped, removed = load_distances(input_path, args.max_distance_km)
        if not distances:
            raise SystemExit("No valid distances found. Check latitude/longitude columns.")
        plot_histogram(distances, output_path)
        print(f"Rows with distance: {len(distances)}")
        print(f"Rows skipped: {skipped}")
        print(f"Rows removed (> {args.max_distance_km} km): {removed}")
        print(f"Histogram saved: {output_path}")


if __name__ == "__main__":
    main()
