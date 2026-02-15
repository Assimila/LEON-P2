"""
Visualize annual burn-any mosaics as red dots with country borders.

Run:
  python3 fire/visualize_burn_any_annual.py --start-year 2001 --end-year 2024

Notes:
- Expects yearly mosaics at fire/mosaics/mcd64a1_burn_any_<YEAR>_idn_mys_cog.tif
- Requires: rasterio, numpy, geopandas, matplotlib
"""

import argparse
import os
from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt
import fiona
from shapely.geometry import shape, Polygon, MultiPolygon
import importlib.util

SCRIPT_DIR = Path(__file__).resolve().parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot annual burn-any mosaics with red fire dots."
    )
    parser.add_argument("--start-year", type=int, default=2001)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--input-dir",
        default=str(SCRIPT_DIR / "mosaics"),
        help="Directory containing yearly COGs.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(SCRIPT_DIR / "figures"),
        help="Directory to write PNGs.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=2000000,
        help="Max number of fire pixels to plot per year (random sample if exceeded).",
    )
    parser.add_argument(
        "--point-size",
        type=float,
        default=1.0,
        help="Scatter point size for fire dots.",
    )
    parser.add_argument(
        "--border-linewidth",
        type=float,
        default=0.6,
        help="Line width for country borders.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for subsampling.",
    )
    parser.add_argument(
        "--trend-out",
        default=str(SCRIPT_DIR / "figures" / "burn_any_annual_change.png"),
        help="Output path for annual change plot.",
    )
    return parser.parse_args()


def _naturalearth_lowres_path() -> str:
    spec = importlib.util.find_spec("geopandas")
    if spec is None or not spec.submodule_search_locations:
        raise FileNotFoundError("geopandas package not found for Natural Earth dataset.")
    base = list(spec.submodule_search_locations)[0]
    path = os.path.join(
        base, "datasets", "naturalearth_lowres", "naturalearth_lowres.shp"
    )
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Natural Earth shapefile not found: {path}")
    return path


def _load_borders() -> list:
    # Read Natural Earth low-res with Fiona to avoid geopandas/shapely version issues.
    shp_path = _naturalearth_lowres_path()
    borders = []
    with fiona.open(shp_path) as src:
        for feat in src:
            if feat["properties"].get("name") in ("Indonesia", "Malaysia"):
                geom = shape(feat["geometry"])
                borders.append(geom)
    return borders


def _borders_bounds(borders: list) -> tuple[float, float, float, float]:
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    for geom in borders:
        bx, by, Bx, By = geom.bounds
        minx = min(minx, bx)
        miny = min(miny, by)
        maxx = max(maxx, Bx)
        maxy = max(maxy, By)
    return minx, miny, maxx, maxy


def _plot_borders(ax: plt.Axes, borders: list, linewidth: float) -> None:
    for geom in borders:
        if isinstance(geom, Polygon):
            x, y = geom.exterior.xy
            ax.plot(x, y, color="black", linewidth=linewidth)
        elif isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                x, y = poly.exterior.xy
                ax.plot(x, y, color="black", linewidth=linewidth)


def _fire_points_and_area(
    raster_path: str, max_points: int, seed: int
) -> tuple[np.ndarray, np.ndarray, float | None]:
    with rasterio.open(raster_path) as src:
        band = src.read(1)
        mask = band > 0

        rows, cols = np.where(mask)
        count = rows.size
        if count == 0:
            return np.array([]), np.array([]), 0.0

        if max_points > 0 and count > max_points:
            rng = np.random.default_rng(seed)
            idx = rng.choice(count, size=max_points, replace=False)
            rows = rows[idx]
            cols = cols[idx]

        xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center")
        total_area_km2 = None
        if src.crs is not None and src.crs.is_projected:
            pixel_area_m2 = abs(src.transform.a * src.transform.e)
            total_area_km2 = (count * pixel_area_m2) / 1_000_000.0
        return np.array(xs), np.array(ys), total_area_km2


def main() -> None:
    args = _parse_args()
    if args.end_year < args.start_year:
        raise ValueError("--end-year must be >= --start-year.")

    os.makedirs(args.out_dir, exist_ok=True)
    borders = _load_borders()
    minx, miny, maxx, maxy = _borders_bounds(borders)
    pad_x = (maxx - minx) * 0.02
    pad_y = (maxy - miny) * 0.02
    xlim = (minx - pad_x, maxx + pad_x)
    ylim = (miny - pad_y, maxy + pad_y)

    years = []
    totals = []
    totals_label = "Burned area (km^2)"

    for year in range(args.start_year, args.end_year + 1):
        raster_path = os.path.join(
            args.input_dir, f"mcd64a1_burn_any_{year}_idn_mys_cog.tif"
        )
        if not os.path.isfile(raster_path):
            print(f"Missing raster, skipping: {raster_path}")
            continue

        xs, ys, total_area_km2 = _fire_points_and_area(
            raster_path, args.max_points, args.seed
        )

        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_axes([0.08, 0.08, 0.84, 0.84])
        _plot_borders(ax, borders, args.border_linewidth)

        if xs.size > 0:
            ax.scatter(xs, ys, s=args.point_size, c="red", marker="o", linewidths=0)

        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_title(f"Annual Fire (Burn Any) {year}")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal", adjustable="box")

        out_path = os.path.join(args.out_dir, f"burn_any_{year}.png")
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        print(f"Wrote {out_path}")

        if total_area_km2 is None:
            totals_label = "Burned pixels"
            total_value = float((xs.size))
        else:
            total_value = float(total_area_km2)

        years.append(year)
        totals.append(total_value)

    if years:
        fig = plt.figure(figsize=(10, 4))
        ax = fig.add_axes([0.08, 0.18, 0.90, 0.72])
        ax.plot(years, totals, color="red", linewidth=1.5)
        ax.scatter(years, totals, color="red", s=12)
        ax.set_xlabel("Year")
        ax.set_ylabel(totals_label)
        ax.set_title("Annual Burn Change")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)

        fig.savefig(args.trend_out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {args.trend_out}")


if __name__ == "__main__":
    main()
