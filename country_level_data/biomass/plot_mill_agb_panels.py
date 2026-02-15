"""
Plot mill-level AGB panels (2015-2022 by default) for a fixed-radius neighborhood.

Examples:
  conda run -n geospatial python country_level_data/biomass/plot_mill_agb_panels.py \
    --mill-id PO1000000058 \
    --company CARGILL \
    --mill-name HINDOLI \
    --lat -2.612778 --lon 104.128242 \
    --radius-km 50

  conda run -n geospatial python country_level_data/biomass/plot_mill_agb_panels.py \
    --mill-row "PO1000000058\tCARGILL\tHINDOLI\tSUNGAI LILIN\tRSPO Certified\tRSPO Certified, IP\t11/12/2024\t-2.612778\t104.128242\t-2.612778, 104.128242\tIDN\tIndonesia\tSumatera Selatan\tMusi Banyuasin\t2-High Confidence"

Requires: rasterio, numpy, matplotlib (available in the geospatial conda env).
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.ticker import FuncFormatter, MaxNLocator
from rasterio.enums import Resampling
from rasterio.windows import Window, bounds as window_bounds, from_bounds

SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass
class MillInfo:
    mill_id: str
    company: str
    mill_name: str
    lat: float
    lon: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create multi-panel mill-level AGB maps across years."
    )
    parser.add_argument(
        "--mill-row",
        default=None,
        help=(
            "Tab-separated row containing at least columns: mill_id, company, "
            "mill_name, ..., lat (col 8), lon (col 9)."
        ),
    )
    parser.add_argument("--mill-id", default=None, help="Mill ID (e.g., PO1000000058).")
    parser.add_argument("--company", default=None, help="Company name.")
    parser.add_argument("--mill-name", default=None, help="Mill name.")
    parser.add_argument("--lat", type=float, default=None, help="Mill latitude.")
    parser.add_argument("--lon", type=float, default=None, help="Mill longitude.")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2015,
        help="Start year (default: 2015).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2022,
        help="End year (default: 2022).",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=50.0,
        help="Radius around mill to plot, in km (default: 50).",
    )
    parser.add_argument(
        "--target-pixels",
        type=int,
        default=900,
        help="Max pixel width/height per panel after resampling (default: 900).",
    )
    parser.add_argument(
        "--mosaics-dir",
        default=str(SCRIPT_DIR / "mosaics"),
        help="Directory with yearly mosaic files agb_<year>_idn_mys_cog.tif.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(SCRIPT_DIR / "figures"),
        help="Directory for output PNG.",
    )
    parser.add_argument(
        "--out-path",
        default=None,
        help="Optional explicit output PNG path.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=220,
        help="Output image DPI (default: 220).",
    )
    return parser.parse_args()


def _parse_mill_row(row: str) -> MillInfo:
    cols = row.strip().split("\t")
    if len(cols) < 9:
        raise ValueError(
            "--mill-row must have at least 9 tab-separated columns including lat/lon."
        )
    return MillInfo(
        mill_id=cols[0].strip() or "UNKNOWN_MILL",
        company=cols[1].strip() if len(cols) > 1 else "UNKNOWN_COMPANY",
        mill_name=cols[2].strip() if len(cols) > 2 else "UNKNOWN_MILL_NAME",
        lat=float(cols[7]),
        lon=float(cols[8]),
    )


def _resolve_mill_info(args: argparse.Namespace) -> MillInfo:
    if args.mill_row:
        parsed = _parse_mill_row(args.mill_row)
    else:
        parsed = MillInfo(
            mill_id=args.mill_id or "UNKNOWN_MILL",
            company=args.company or "UNKNOWN_COMPANY",
            mill_name=args.mill_name or "UNKNOWN_MILL_NAME",
            lat=args.lat if args.lat is not None else float("nan"),
            lon=args.lon if args.lon is not None else float("nan"),
        )

    mill_id = args.mill_id if args.mill_id is not None else parsed.mill_id
    company = args.company if args.company is not None else parsed.company
    mill_name = args.mill_name if args.mill_name is not None else parsed.mill_name
    lat = args.lat if args.lat is not None else parsed.lat
    lon = args.lon if args.lon is not None else parsed.lon

    if not np.isfinite(lat) or not np.isfinite(lon):
        raise ValueError("Mill coordinates are required. Provide --lat and --lon or --mill-row.")
    return MillInfo(
        mill_id=mill_id,
        company=company,
        mill_name=mill_name,
        lat=float(lat),
        lon=float(lon),
    )


def _radius_bounds(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    lat_deg = radius_km / 110.574
    cos_lat = max(1e-6, math.cos(math.radians(lat)))
    lon_deg = radius_km / (111.320 * cos_lat)
    min_lon = lon - lon_deg
    max_lon = lon + lon_deg
    min_lat = lat - lat_deg
    max_lat = lat + lat_deg
    return min_lon, min_lat, max_lon, max_lat


def _safe_window(
    src: rasterio.DatasetReader, min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> Window:
    win = from_bounds(min_lon, min_lat, max_lon, max_lat, src.transform)
    win = win.round_offsets().round_lengths()
    full = Window(0, 0, src.width, src.height)
    return win.intersection(full)


def _read_panel_data(
    tif_path: str,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    target_pixels: int,
    mill_lat: float,
    mill_lon: float,
    radius_km: float,
) -> tuple[np.ndarray, list[float]]:
    with rasterio.open(tif_path) as src:
        win = _safe_window(src, min_lon, min_lat, max_lon, max_lat)
        if win.width <= 0 or win.height <= 0:
            raise ValueError(f"Computed empty window for raster: {tif_path}")

        scale = max(win.width / target_pixels, win.height / target_pixels, 1.0)
        out_h = max(1, int(win.height / scale))
        out_w = max(1, int(win.width / scale))

        arr = src.read(
            1,
            window=win,
            out_shape=(out_h, out_w),
            resampling=Resampling.bilinear,
        ).astype("float32")

        nodata = src.nodata
        valid = np.isfinite(arr)
        if nodata is not None:
            valid &= arr != nodata
        valid &= arr > 0

        left, bottom, right, top = window_bounds(win, src.transform)
        extent = [left, right, bottom, top]

        # Keep only pixels inside the circular supply shed.
        xres = (right - left) / out_w
        yres = (top - bottom) / out_h
        xs = left + (np.arange(out_w, dtype="float32") + 0.5) * xres
        ys = top - (np.arange(out_h, dtype="float32") + 0.5) * yres
        xx, yy = np.meshgrid(xs, ys)

        dx_km = (xx - mill_lon) * (111.320 * math.cos(math.radians(mill_lat)))
        dy_km = (yy - mill_lat) * 110.574
        in_shed = (dx_km * dx_km + dy_km * dy_km) <= (radius_km * radius_km)

        arr = np.where(valid & in_shed, arr, np.nan)
        return arr, extent


def _degree_lon(x: float, _pos: float) -> str:
    if x > 0:
        return f"{abs(x):.2f}\N{DEGREE SIGN}E"
    if x < 0:
        return f"{abs(x):.2f}\N{DEGREE SIGN}W"
    return f"0\N{DEGREE SIGN}"


def _degree_lat(y: float, _pos: float) -> str:
    if y > 0:
        return f"{abs(y):.2f}\N{DEGREE SIGN}N"
    if y < 0:
        return f"{abs(y):.2f}\N{DEGREE SIGN}S"
    return f"0\N{DEGREE SIGN}"


def _radius_outline_points(lat: float, lon: float, radius_km: float, n: int = 180) -> np.ndarray:
    lat_radius = radius_km / 110.574
    lon_radius = radius_km / (111.320 * max(1e-6, math.cos(math.radians(lat))))
    thetas = np.linspace(0, 2 * math.pi, n)
    xs = lon + lon_radius * np.cos(thetas)
    ys = lat + lat_radius * np.sin(thetas)
    return np.column_stack([xs, ys])


def _existing_years(start_year: int, end_year: int, mosaics_dir: str) -> list[int]:
    years = []
    for year in range(start_year, end_year + 1):
        tif = os.path.join(mosaics_dir, f"agb_{year}_idn_mys_cog.tif")
        if os.path.isfile(tif):
            years.append(year)
    return years


def _flatten_valid(arrays: Iterable[np.ndarray]) -> np.ndarray:
    pieces = [a[np.isfinite(a)] for a in arrays]
    pieces = [p for p in pieces if p.size > 0]
    if not pieces:
        return np.array([], dtype="float32")
    return np.concatenate(pieces).astype("float32")


def main() -> None:
    args = _parse_args()
    if args.end_year < args.start_year:
        raise ValueError("--end-year must be >= --start-year.")

    mill = _resolve_mill_info(args)
    years = _existing_years(args.start_year, args.end_year, args.mosaics_dir)
    if not years:
        raise FileNotFoundError(
            f"No yearly mosaics found in {args.mosaics_dir} for {args.start_year}-{args.end_year}."
        )

    min_lon, min_lat, max_lon, max_lat = _radius_bounds(mill.lat, mill.lon, args.radius_km)
    arrays: list[np.ndarray] = []
    extents: list[list[float]] = []
    for year in years:
        tif = os.path.join(args.mosaics_dir, f"agb_{year}_idn_mys_cog.tif")
        arr, extent = _read_panel_data(
            tif,
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            target_pixels=args.target_pixels,
            mill_lat=mill.lat,
            mill_lon=mill.lon,
            radius_km=args.radius_km,
        )
        arrays.append(arr)
        extents.append(extent)

    valid_all = _flatten_valid(arrays)
    if valid_all.size == 0:
        raise ValueError("No valid AGB values found in the selected mill neighborhood.")

    vmin = float(np.nanpercentile(valid_all, 2))
    vmax = float(np.nanpercentile(valid_all, 98))
    if vmin >= vmax:
        vmin, vmax = float(np.nanmin(valid_all)), float(np.nanmax(valid_all))

    cols = 4
    rows = int(math.ceil(len(years) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 4.3 * rows), dpi=args.dpi)
    axes = np.atleast_1d(axes).ravel()

    circle_xy = _radius_outline_points(mill.lat, mill.lon, args.radius_km)
    mappable = None
    for i, year in enumerate(years):
        ax = axes[i]
        mappable = ax.imshow(
            arrays[i],
            extent=extents[i],
            origin="upper",
            cmap="YlGn",
            vmin=vmin,
            vmax=vmax,
        )
        ax.add_patch(
            MplPolygon(
                circle_xy,
                closed=True,
                fill=False,
                edgecolor="black",
                linewidth=1.0,
                linestyle="--",
                zorder=3,
            )
        )
        ax.scatter([mill.lon], [mill.lat], s=22, c="red", marker="x", linewidths=1.2, zorder=4)
        ax.set_title(str(year), fontsize=14)
        ax.set_aspect("equal")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.xaxis.set_major_formatter(FuncFormatter(_degree_lon))
        ax.yaxis.set_major_formatter(FuncFormatter(_degree_lat))
        ax.tick_params(axis="both", labelsize=10)
        if i % cols == 0:
            ax.set_ylabel("Latitude", fontsize=12)
        if i >= (rows - 1) * cols:
            ax.set_xlabel("Longitude", fontsize=12)

    for j in range(len(years), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(
        (
            f"Mill-level AGB (radius {args.radius_km:.0f} km): "
            f"{mill.mill_id} | {mill.company} | {mill.mill_name}"
        ),
        fontsize=18,
        y=0.995,
    )

    fig.subplots_adjust(right=0.92, top=0.90, wspace=0.14, hspace=0.20)
    cax = fig.add_axes([0.935, 0.13, 0.015, 0.72])
    cbar = fig.colorbar(mappable, cax=cax)
    cbar.set_label("AGB (Mg/ha)", fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    os.makedirs(args.out_dir, exist_ok=True)
    if args.out_path:
        out_path = args.out_path
    else:
        out_name = f"mill_agb_panels_{mill.mill_id}_{years[0]}_{years[-1]}_r{int(args.radius_km)}km.png"
        out_path = os.path.join(args.out_dir, out_name)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {out_path}")
    print(f"Years: {years[0]}-{years[-1]} ({len(years)} panels)")
    print(f"Mill: {mill.mill_id} ({mill.lat:.6f}, {mill.lon:.6f})")


if __name__ == "__main__":
    main()
