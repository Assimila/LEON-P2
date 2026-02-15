"""
Plot cumulative fire frequency for Indonesia + Malaysia from annual burn-any mosaics.

Example:
  conda run -n geospatial python country_level_data/fire/plot_fire_frequency.py \
    --start-year 2001 --end-year 2024
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import warnings

from cartopy.io import shapereader
import fiona
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.ticker import FuncFormatter, MaxNLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable
from rasterio.enums import Resampling
from shapely.geometry import MultiPolygon, Polygon, shape

SCRIPT_DIR = Path(__file__).resolve().parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a single fire-frequency map by combining annual burn-any rasters."
    )
    parser.add_argument("--start-year", type=int, default=2001)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--boundary-resolution",
        default="10m",
        choices=["10m", "50m", "110m", "lowres"],
        help="Country boundary resolution. Default: 10m.",
    )
    parser.add_argument(
        "--input-dir",
        default=str(SCRIPT_DIR / "mosaics"),
        help="Directory containing yearly COGs: mcd64a1_burn_any_<YEAR>_idn_mys_cog.tif",
    )
    parser.add_argument(
        "--out-path",
        default=str(SCRIPT_DIR / "figures" / "fire_frequency_2001_2024_idn_mys.png"),
        help="Output PNG path.",
    )
    parser.add_argument(
        "--target-width",
        type=int,
        default=2600,
        help="Resampled raster width for plotting/aggregation (default: 2600).",
    )
    parser.add_argument(
        "--hide-zero",
        action="store_true",
        help="Mask pixels with zero fire frequency (clear background where no fire incidence).",
    )
    parser.add_argument(
        "--vmax",
        type=float,
        default=None,
        help="Optional fixed max for colorbar in percent. Default uses percentile.",
    )
    parser.add_argument(
        "--vmax-percentile",
        type=float,
        default=99.0,
        help="Percentile-based vmax when --vmax is not provided (default: 99).",
    )
    parser.add_argument("--dpi", type=int, default=240)
    return parser.parse_args()


def _naturalearth_lowres_path() -> str:
    import importlib.util

    spec = importlib.util.find_spec("geopandas")
    if spec is None or not spec.submodule_search_locations:
        raise FileNotFoundError("geopandas package not found for Natural Earth low-res dataset.")
    base = list(spec.submodule_search_locations)[0]
    shp = os.path.join(base, "datasets", "naturalearth_lowres", "naturalearth_lowres.shp")
    if not os.path.isfile(shp):
        raise FileNotFoundError(f"Natural Earth low-res shapefile not found: {shp}")
    return shp


def _naturalearth_country_path(boundary_resolution: str) -> str:
    if boundary_resolution == "lowres":
        return _naturalearth_lowres_path()

    try:
        return shapereader.natural_earth(
            resolution=boundary_resolution,
            category="cultural",
            name="admin_0_countries",
        )
    except Exception as exc:
        warnings.warn(
            f"Could not load Natural Earth {boundary_resolution} boundaries ({exc}); "
            "falling back to geopandas lowres boundaries."
        )
        return _naturalearth_lowres_path()


def _country_name(props: dict) -> str:
    for key in ("ADMIN", "NAME", "NAME_LONG", "SOVEREIGNT", "name"):
        val = props.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _load_borders(boundary_resolution: str) -> list[Polygon | MultiPolygon]:
    shp = _naturalearth_country_path(boundary_resolution)
    borders: list[Polygon | MultiPolygon] = []
    with fiona.open(shp) as src:
        for feat in src:
            cname = _country_name(feat["properties"])
            if cname in ("Indonesia", "Malaysia"):
                borders.append(shape(feat["geometry"]))
    if not borders:
        raise ValueError(f"No Indonesia/Malaysia features found in boundary file: {shp}")
    return borders


def _plot_borders(ax: plt.Axes, borders: list[Polygon | MultiPolygon], lw: float = 0.8) -> None:
    for geom in borders:
        if isinstance(geom, Polygon):
            x, y = geom.exterior.xy
            ax.plot(x, y, color="black", linewidth=lw, zorder=3)
        elif isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                x, y = poly.exterior.xy
                ax.plot(x, y, color="black", linewidth=lw, zorder=3)


def _degree_lon(x: float, _pos: float) -> str:
    if x > 0:
        return f"{abs(x):.0f}\N{DEGREE SIGN}E"
    if x < 0:
        return f"{abs(x):.0f}\N{DEGREE SIGN}W"
    return f"0\N{DEGREE SIGN}"


def _degree_lat(y: float, _pos: float) -> str:
    if y > 0:
        return f"{abs(y):.0f}\N{DEGREE SIGN}N"
    if y < 0:
        return f"{abs(y):.0f}\N{DEGREE SIGN}S"
    return f"0\N{DEGREE SIGN}"


def _collect_year_files(start_year: int, end_year: int, input_dir: str) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    for year in range(start_year, end_year + 1):
        path = os.path.join(input_dir, f"mcd64a1_burn_any_{year}_idn_mys_cog.tif")
        if os.path.isfile(path):
            items.append((year, path))
    return items


def _accumulate_frequency(
    year_files: list[tuple[int, str]],
    target_width: int,
) -> tuple[np.ndarray, list[float], int]:
    if not year_files:
        raise ValueError("No yearly raster files found.")

    first_path = year_files[0][1]
    with rasterio.open(first_path) as src0:
        w0, h0 = src0.width, src0.height
        scale = w0 / target_width if w0 > target_width else 1.0
        out_w = max(1, int(w0 / scale))
        out_h = max(1, int(h0 / scale))
        bounds = src0.bounds
        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    count = np.zeros((out_h, out_w), dtype=np.uint16)
    n_years = 0
    for year, path in year_files:
        with rasterio.open(path) as src:
            arr = src.read(
                1,
                out_shape=(out_h, out_w),
                resampling=Resampling.nearest,
            )
        count += (arr > 0).astype(np.uint16)
        n_years += 1
        print(f"Accumulated {year}")

    freq_pct = (count.astype(np.float32) / float(n_years)) * 100.0
    return freq_pct, extent, n_years


def main() -> None:
    args = _parse_args()
    if args.end_year < args.start_year:
        raise ValueError("--end-year must be >= --start-year.")

    year_files = _collect_year_files(args.start_year, args.end_year, args.input_dir)
    if not year_files:
        raise FileNotFoundError(
            f"No burn-any mosaics found in {args.input_dir} for {args.start_year}-{args.end_year}."
        )
    years = [y for y, _ in year_files]
    print(f"Using {len(years)} years: {years[0]}-{years[-1]}")

    freq_pct, extent, n_years = _accumulate_frequency(
        year_files=year_files,
        target_width=args.target_width,
    )

    if args.hide_zero:
        freq_plot = np.where(freq_pct > 0, freq_pct, np.nan)
    else:
        freq_plot = freq_pct

    finite = freq_plot[np.isfinite(freq_plot)]
    if finite.size == 0:
        raise ValueError("No finite values to plot. Try without --hide-zero.")

    vmin = 0.0
    if args.vmax is not None:
        vmax = float(args.vmax)
    else:
        vmax = float(np.nanpercentile(freq_plot, args.vmax_percentile))
        vmax = max(vmax, 1.0)

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    borders = _load_borders(args.boundary_resolution)

    fig, ax = plt.subplots(figsize=(12, 7.2), dpi=args.dpi)
    im = ax.imshow(
        freq_plot,
        extent=extent,
        origin="upper",
        cmap="YlOrRd",
        vmin=vmin,
        vmax=vmax,
    )
    _plot_borders(ax, borders, lw=0.8)

    ax.set_title(
        f"Fire Frequency (Burned Any) {years[0]}-{years[-1]}: Indonesia + Malaysia",
        fontsize=20,
        pad=10,
    )
    ax.set_xlabel("Longitude", fontsize=16)
    ax.set_ylabel("Latitude", fontsize=16)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=8))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=7))
    ax.xaxis.set_major_formatter(FuncFormatter(_degree_lon))
    ax.yaxis.set_major_formatter(FuncFormatter(_degree_lat))
    ax.tick_params(axis="both", labelsize=13)
    ax.set_aspect("equal", adjustable="box")

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3.5%", pad=0.08)
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(f"Fire frequency (% of {n_years} years)", fontsize=14)
    cbar.ax.tick_params(labelsize=12)

    fig.tight_layout()
    fig.savefig(args.out_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {args.out_path}")


if __name__ == "__main__":
    main()
