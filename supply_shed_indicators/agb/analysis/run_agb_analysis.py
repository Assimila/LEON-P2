#!/usr/bin/env python3
from __future__ import annotations
import os

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.coords import BoundingBox
from rasterio.windows import Window, from_bounds


# Repository root (override with the LEON_P2_ROOT environment variable).
PROJECT_ROOT = Path(os.environ.get("LEON_P2_ROOT", Path(__file__).resolve().parents[3]))
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'configs' / 'default.json'

GROUP_COLORS = {
    'ALL_MILLS': '#0072B2',
    'MATCHED_H2_2024': '#D55E00',
}


@dataclass(frozen=True)
class Config:
    experiment_name: str
    mills_csv: Path
    matched_mills_csv: Path
    mosaics_dir: Path
    year_start: int
    year_end: int
    radii_km: tuple[float, ...]
    nodata_value: float
    output_root: Path


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def load_config(path: Path) -> Config:
    raw = json.loads(path.read_text(encoding='utf-8'))
    return Config(
        experiment_name=str(raw['experiment_name']),
        mills_csv=_resolve_path(raw['mills_csv']),
        matched_mills_csv=_resolve_path(raw['matched_mills_csv']),
        mosaics_dir=_resolve_path(raw['mosaics_dir']),
        year_start=int(raw['year_start']),
        year_end=int(raw['year_end']),
        radii_km=tuple(float(x) for x in raw['radii_km']),
        nodata_value=float(raw.get('nodata_value', -9999.0)),
        output_root=_resolve_path(raw['output_root']),
    )


def _read_csv_fallback(path: Path) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ('utf-8', 'utf-8-sig', 'latin1', 'cp1252'):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as exc:
            last = exc
    raise RuntimeError(f'Failed to read CSV {path}: {last}')


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = out.columns.str.strip().str.lower().str.replace(r'\s+', '_', regex=True)
    return out


def _parse_coord(value: object, *, is_lat: bool) -> float:
    if pd.isna(value):
        return float('nan')
    s = str(value).strip().replace('\xa0', '').replace(' ', '')
    if not s:
        return float('nan')
    if ',' in s and '.' not in s and s.count(',') == 1:
        s = s.replace(',', '.')
    elif ',' in s and '.' in s:
        s = s.replace(',', '')
    try:
        num = float(s)
    except ValueError:
        return float('nan')

    limit = 90.0 if is_lat else 180.0
    if abs(num) > limit and abs(num) <= (90_000_000 if is_lat else 180_000_000):
        num = num / 1_000_000.0
    return num


def load_mills(path: Path, *, limit: int | None = None) -> pd.DataFrame:
    df = _norm_cols(_read_csv_fallback(path))
    required = ['uml_id', 'mill_name', 'latitude', 'longitude', 'iso', 'country']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'Missing required mill columns: {missing}')

    out = pd.DataFrame({
        'mill_id': df['uml_id'].astype(str).str.strip(),
        'mill_name': df['mill_name'].astype(str).str.strip(),
        'latitude': df['latitude'].map(lambda v: _parse_coord(v, is_lat=True)),
        'longitude': df['longitude'].map(lambda v: _parse_coord(v, is_lat=False)),
        'iso': df['iso'].astype(str).str.strip(),
        'country': df['country'].astype(str).str.strip(),
    })
    out = out.dropna(subset=['latitude', 'longitude'])
    out = out[out['latitude'].between(-90, 90) & out['longitude'].between(-180, 180)]
    if limit is not None and limit > 0:
        out = out.head(limit)
    return out.reset_index(drop=True)


def load_matched_ids(path: Path) -> set[str]:
    df = _norm_cols(_read_csv_fallback(path))
    for cand in ('uml_id', 'mill_id', 'id'):
        if cand in df.columns:
            return set(df[cand].astype(str).str.strip().unique())
    raise ValueError('No matched mill id column found (expected uml_id/mill_id/id)')


def discover_year_files(mosaics_dir: Path, year_start: int, year_end: int) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for y in range(year_start, year_end + 1):
        p = mosaics_dir / f'agb_{y}_idn_mys_cog.tif'
        if p.exists():
            out[y] = p
    if not out:
        raise FileNotFoundError(f'No AGB COG files found in {mosaics_dir} for {year_start}-{year_end}')
    return out


def validate_year_rasters(year_files: dict[int, Path]) -> None:
    years = sorted(year_files)
    with rasterio.open(year_files[years[0]]) as base:
        base_meta = (base.width, base.height, base.transform, base.crs, base.count)
        for y in years[1:]:
            with rasterio.open(year_files[y]) as ds:
                meta = (ds.width, ds.height, ds.transform, ds.crs, ds.count)
                if meta != base_meta:
                    raise ValueError(f'Raster mismatch for year {y}')


def supply_shed_area_ha(radius_km: float) -> float:
    return math.pi * radius_km * radius_km * 100.0


def circle_bounds_deg(lon: float, lat: float, radius_km: float) -> tuple[float, float, float, float]:
    cos_lat = max(abs(math.cos(math.radians(lat))), 1e-6)
    dlat = radius_km / 110.574
    dlon = radius_km / (111.320 * cos_lat)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def classify_coverage(circle_bounds: tuple[float, float, float, float], raster_bounds: BoundingBox) -> str:
    left, bottom, right, top = circle_bounds
    if right <= raster_bounds.left or left >= raster_bounds.right or top <= raster_bounds.bottom or bottom >= raster_bounds.top:
        return 'NO_COVERAGE'
    if left >= raster_bounds.left and right <= raster_bounds.right and bottom >= raster_bounds.bottom and top <= raster_bounds.top:
        return 'FULL_COVERAGE'
    return 'PARTIAL_COVERAGE'


def integer_window(left: float, bottom: float, right: float, top: float, ds: rasterio.DatasetReader) -> Window:
    win = from_bounds(left, bottom, right, top, transform=ds.transform)
    c0 = int(math.floor(win.col_off))
    r0 = int(math.floor(win.row_off))
    c1 = int(math.ceil(win.col_off + win.width))
    r1 = int(math.ceil(win.row_off + win.height))
    return Window(c0, r0, max(1, c1 - c0), max(1, r1 - r0))


def inside_circle_mask(window: Window, transform: rasterio.Affine, *, lat: float, lon: float, radius_km: float) -> tuple[np.ndarray, float]:
    h = int(window.height)
    w = int(window.width)

    cols = np.arange(w, dtype=np.float64) + float(window.col_off)
    rows = np.arange(h, dtype=np.float64) + float(window.row_off)

    x = transform.c + (cols + 0.5) * transform.a
    y = transform.f + (rows + 0.5) * transform.e

    m_per_deg_lon = 111_320.0 * max(abs(math.cos(math.radians(lat))), 1e-6)
    dx2 = np.square((x - lon) * m_per_deg_lon)
    dy2 = np.square((y - lat) * 110_574.0)
    radius_m2 = (radius_km * 1000.0) ** 2
    inside = (dy2[:, None] + dx2[None, :]) <= radius_m2

    pixel_area_m2 = abs(transform.a) * 111_320.0 * max(abs(math.cos(math.radians(lat))), 1e-6) * abs(transform.e) * 110_574.0
    pixel_area_ha = pixel_area_m2 / 10_000.0
    return inside, pixel_area_ha


def summarize_agb(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {
            'agb_mean_mg_ha': np.nan,
            'agb_median_mg_ha': np.nan,
            'agb_std_mg_ha': np.nan,
            'agb_min_mg_ha': np.nan,
            'agb_p10_mg_ha': np.nan,
            'agb_p90_mg_ha': np.nan,
            'agb_max_mg_ha': np.nan,
        }

    return {
        'agb_mean_mg_ha': float(np.nanmean(values)),
        'agb_median_mg_ha': float(np.nanmedian(values)),
        'agb_std_mg_ha': float(np.nanstd(values, ddof=1)) if values.size > 1 else np.nan,
        'agb_min_mg_ha': float(np.nanmin(values)),
        'agb_p10_mg_ha': float(np.nanpercentile(values, 10)),
        'agb_p90_mg_ha': float(np.nanpercentile(values, 90)),
        'agb_max_mg_ha': float(np.nanmax(values)),
    }


def extract_all_stats(cfg: Config, *, limit: int | None = None) -> tuple[pd.DataFrame, dict[int, Path]]:
    mills = load_mills(cfg.mills_csv, limit=limit)
    year_files = discover_year_files(cfg.mosaics_dir, cfg.year_start, cfg.year_end)
    validate_year_rasters(year_files)

    years = sorted(year_files)
    datasets = {y: rasterio.open(year_files[y]) for y in years}
    base_ds = datasets[years[0]]

    records: list[dict[str, Any]] = []
    total_combo = len(mills) * len(cfg.radii_km)
    combo_idx = 0

    try:
        for mill in mills.itertuples(index=False):
            for radius_km in cfg.radii_km:
                combo_idx += 1
                if combo_idx % 20 == 0 or combo_idx == total_combo:
                    print(f'[extract] {combo_idx}/{total_combo} mill-radius combinations processed', flush=True)

                lon = float(mill.longitude)
                lat = float(mill.latitude)
                shed_area_ha = supply_shed_area_ha(float(radius_km))
                cb = circle_bounds_deg(lon, lat, float(radius_km))
                coverage = classify_coverage(cb, base_ds.bounds)

                if coverage == 'NO_COVERAGE':
                    for y in years:
                        records.append({
                            'mill_id': str(mill.mill_id),
                            'mill_name': str(mill.mill_name),
                            'iso': str(mill.iso),
                            'country': str(mill.country),
                            'latitude': lat,
                            'longitude': lon,
                            'radius_km': float(radius_km),
                            'year': int(y),
                            'coverage_status': coverage,
                            'supply_shed_area_ha': shed_area_ha,
                            'pixel_area_ha': np.nan,
                            'inside_pixel_count': np.nan,
                            'valid_pixel_count': np.nan,
                            'valid_area_ha': np.nan,
                            'valid_area_pct_of_shed': np.nan,
                            'agb_total_biomass_mg': np.nan,
                            'agb_mean_mg_ha': np.nan,
                            'agb_median_mg_ha': np.nan,
                            'agb_std_mg_ha': np.nan,
                            'agb_min_mg_ha': np.nan,
                            'agb_p10_mg_ha': np.nan,
                            'agb_p90_mg_ha': np.nan,
                            'agb_max_mg_ha': np.nan,
                        })
                    continue

                left, bottom, right, top = cb
                win = integer_window(left, bottom, right, top, base_ds)
                inside, pixel_area_ha = inside_circle_mask(win, base_ds.transform, lat=lat, lon=lon, radius_km=float(radius_km))
                inside_px = int(np.count_nonzero(inside))

                for y in years:
                    arr = datasets[y].read(
                        1,
                        window=win,
                        boundless=True,
                        fill_value=np.nan,
                        out_dtype=np.float32,
                    )
                    valid = inside & np.isfinite(arr) & (arr > 0)
                    vals = arr[valid].astype(np.float64)
                    valid_px = int(vals.size)
                    valid_area_ha = valid_px * pixel_area_ha
                    valid_pct = (valid_area_ha / shed_area_ha * 100.0) if shed_area_ha > 0 else np.nan

                    stats = summarize_agb(vals)
                    agb_total = float(np.sum(vals) * pixel_area_ha) if valid_px > 0 else np.nan

                    records.append({
                        'mill_id': str(mill.mill_id),
                        'mill_name': str(mill.mill_name),
                        'iso': str(mill.iso),
                        'country': str(mill.country),
                        'latitude': lat,
                        'longitude': lon,
                        'radius_km': float(radius_km),
                        'year': int(y),
                        'coverage_status': coverage,
                        'supply_shed_area_ha': shed_area_ha,
                        'pixel_area_ha': pixel_area_ha,
                        'inside_pixel_count': inside_px,
                        'valid_pixel_count': valid_px,
                        'valid_area_ha': valid_area_ha,
                        'valid_area_pct_of_shed': valid_pct,
                        'agb_total_biomass_mg': agb_total,
                        **stats,
                    })

    finally:
        for ds in datasets.values():
            ds.close()

    return pd.DataFrame(records), year_files


def summarize_metric(grouped: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (radius, year, group), sub in grouped.groupby(['radius_km', 'year', 'group'], sort=True):
        s = pd.to_numeric(sub[metric], errors='coerce').dropna()
        n = int(len(s))
        std = float(s.std(ddof=1)) if n > 1 else np.nan
        se = std / np.sqrt(n) if n > 1 else np.nan
        ci95 = 1.96 * se if n > 1 else np.nan
        rows.append({
            'radius_km': float(radius),
            'year': int(year),
            'group': group,
            'metric': metric,
            'n_non_null': n,
            'mean': float(s.mean()) if n else np.nan,
            'median': float(s.median()) if n else np.nan,
            'std': std,
            'min': float(s.min()) if n else np.nan,
            'p25': float(s.quantile(0.25)) if n else np.nan,
            'p75': float(s.quantile(0.75)) if n else np.nan,
            'max': float(s.max()) if n else np.nan,
            'ci95': ci95,
        })
    return pd.DataFrame(rows)


def compute_per_mill_change(df: pd.DataFrame, year_start: int, year_end: int) -> pd.DataFrame:
    # Build the full mill x radius index so NO_COVERAGE mills are preserved.
    all_keys = df[['mill_id', 'radius_km']].drop_duplicates().reset_index(drop=True)

    keep = ['mill_id', 'radius_km', 'year', 'agb_mean_mg_ha']
    x = df[keep].copy()
    p = x.pivot_table(index=['mill_id', 'radius_km'], columns='year', values='agb_mean_mg_ha', aggfunc='first')
    p = p.reset_index()
    p = all_keys.merge(p, on=['mill_id', 'radius_km'], how='left')

    p['agb_mean_start'] = p.get(year_start, np.nan)
    p['agb_mean_end'] = p.get(year_end, np.nan)
    p['agb_delta_end_minus_start_mg_ha'] = p['agb_mean_end'] - p['agb_mean_start']
    p['agb_pct_change_end_vs_start'] = np.where(
        p['agb_mean_start'] > 0,
        (p['agb_mean_end'] - p['agb_mean_start']) / p['agb_mean_start'] * 100.0,
        np.nan,
    )
    span = year_end - year_start
    p['agb_cagr_pct'] = np.where(
        (p['agb_mean_start'] > 0) & (p['agb_mean_end'] > 0) & (span > 0),
        ((p['agb_mean_end'] / p['agb_mean_start']) ** (1.0 / span) - 1.0) * 100.0,
        np.nan,
    )

    # Linear slope across all years per mill/radius.
    slopes = []
    for (mill_id, radius), sub in df.groupby(['mill_id', 'radius_km']):
        y = sub[['year', 'agb_mean_mg_ha']].dropna().sort_values('year')
        if len(y) >= 2:
            slope = float(np.polyfit(y['year'].to_numpy(), y['agb_mean_mg_ha'].to_numpy(), 1)[0])
        else:
            slope = np.nan
        slopes.append({'mill_id': mill_id, 'radius_km': radius, 'agb_trend_slope_mg_ha_per_year': slope})
    slopes_df = pd.DataFrame(slopes)

    return p.merge(slopes_df, on=['mill_id', 'radius_km'], how='left')


def summarize_change_by_group(change_df: pd.DataFrame, matched_ids: set[str]) -> pd.DataFrame:
    base = change_df.copy()
    base['group'] = np.where(base['mill_id'].isin(matched_ids), 'MATCHED_H2_2024', 'ALL_MILLS')

    # all mills summary
    all_rows = []
    for radius, sub_r in base.groupby('radius_km'):
        for metric in ['agb_delta_end_minus_start_mg_ha', 'agb_pct_change_end_vs_start', 'agb_cagr_pct', 'agb_trend_slope_mg_ha_per_year']:
            s = pd.to_numeric(sub_r[metric], errors='coerce').dropna()
            all_rows.append({
                'radius_km': float(radius),
                'group': 'ALL_MILLS',
                'metric': metric,
                'n_non_null': int(len(s)),
                'mean': float(s.mean()) if len(s) else np.nan,
                'median': float(s.median()) if len(s) else np.nan,
                'std': float(s.std(ddof=1)) if len(s) > 1 else np.nan,
                'p25': float(s.quantile(0.25)) if len(s) else np.nan,
                'p75': float(s.quantile(0.75)) if len(s) else np.nan,
            })

    matched = base[base['group'] == 'MATCHED_H2_2024']
    for radius, sub_r in matched.groupby('radius_km'):
        for metric in ['agb_delta_end_minus_start_mg_ha', 'agb_pct_change_end_vs_start', 'agb_cagr_pct', 'agb_trend_slope_mg_ha_per_year']:
            s = pd.to_numeric(sub_r[metric], errors='coerce').dropna()
            all_rows.append({
                'radius_km': float(radius),
                'group': 'MATCHED_H2_2024',
                'metric': metric,
                'n_non_null': int(len(s)),
                'mean': float(s.mean()) if len(s) else np.nan,
                'median': float(s.median()) if len(s) else np.nan,
                'std': float(s.std(ddof=1)) if len(s) > 1 else np.nan,
                'p25': float(s.quantile(0.25)) if len(s) else np.nan,
                'p75': float(s.quantile(0.75)) if len(s) else np.nan,
            })

    return pd.DataFrame(all_rows)


def set_plot_style() -> None:
    plt.rcParams.update({
        'figure.dpi': 120,
        'savefig.dpi': 320,
        'font.family': 'DejaVu Sans',
        'pdf.fonttype': 42,
        'ps.fonttype': 42,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': False,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.frameon': False,
    })


def plot_temporal_trends(summary: pd.DataFrame, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    metrics = ['agb_mean_mg_ha', 'agb_total_biomass_mg']
    metric_titles = {
        'agb_mean_mg_ha': 'Mean AGB (Mg/ha)',
        'agb_total_biomass_mg': 'Total AGB in Supply Shed (Mg)',
    }

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.8), constrained_layout=True)

    for r_idx, radius in enumerate([25.0, 50.0]):
        for m_idx, metric in enumerate(metrics):
            ax = axes[m_idx, r_idx]
            sub = summary[(summary['radius_km'] == radius) & (summary['metric'] == metric)]
            for group in ['ALL_MILLS', 'MATCHED_H2_2024']:
                g = sub[sub['group'] == group].sort_values('year')
                x = g['year'].to_numpy()
                y = g['mean'].to_numpy(dtype=float)
                ax.plot(x, y, marker='o', markersize=4.2, linewidth=2.0, color=GROUP_COLORS[group], label=group.replace('_', ' '))

            ax.set_title(f'{metric_titles[metric]} | {int(radius)} km')
            ax.set_xlabel('Year')
            ax.set_ylabel('Value')
            ax.set_xticks(sorted(sub['year'].unique()))
            ax.spines['left'].set_color('#4a4a4a')
            ax.spines['bottom'].set_color('#4a4a4a')

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=2, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle('Temporal AGB Trends: All Mills vs Matched H2-2024', fontsize=15, y=1.03)
    fig.savefig(out_png, bbox_inches='tight')
    fig.savefig(out_pdf, bbox_inches='tight')
    plt.close(fig)


def plot_change_boxplots(change_with_group: pd.DataFrame, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), constrained_layout=True)

    metrics = [
        ('agb_delta_end_minus_start_mg_ha', 'AGB Change 2022-2015 (Mg/ha)'),
        ('agb_trend_slope_mg_ha_per_year', 'AGB Trend Slope (Mg/ha/year)'),
    ]

    for ax, (metric, title) in zip(axes, metrics):
        data = []
        labels = []
        colors = []
        for radius in [25.0, 50.0]:
            for group in ['ALL_MILLS', 'MATCHED_H2_2024']:
                sub = change_with_group[
                    (change_with_group['radius_km'] == radius) & (change_with_group['group'] == group)
                ][metric].dropna()
                data.append(sub.to_numpy())
                labels.append(f'{int(radius)}km\n{group.replace("_", " ")}')
                colors.append(GROUP_COLORS[group])

        bp = ax.boxplot(
            data,
            patch_artist=True,
            tick_labels=labels,
            widths=0.58,
            showfliers=False,
            whiskerprops={'color': '#4a4a4a', 'linewidth': 0.9},
            capprops={'color': '#4a4a4a', 'linewidth': 0.9},
            boxprops={'edgecolor': '#4a4a4a', 'linewidth': 0.9},
            medianprops={'color': '#1a1a1a', 'linewidth': 1.2},
        )
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.78)
        ax.set_title(title)
        ax.spines['left'].set_color('#4a4a4a')
        ax.spines['bottom'].set_color('#4a4a4a')

    fig.suptitle('Per-mill AGB Change Distribution by Radius and Group', fontsize=14)
    fig.savefig(out_png, bbox_inches='tight')
    fig.savefig(out_pdf, bbox_inches='tight')
    plt.close(fig)


def plot_matched_minus_all_heatmap(summary: pd.DataFrame, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    metric = 'agb_mean_mg_ha'

    piv = summary[summary['metric'] == metric].pivot_table(
        index=['radius_km', 'year'],
        columns='group',
        values='mean',
        aggfunc='first',
    ).reset_index()
    piv['diff'] = piv['MATCHED_H2_2024'] - piv['ALL_MILLS']

    years = sorted(piv['year'].unique())
    radii = [25.0, 50.0]
    mat = np.full((len(radii), len(years)), np.nan)
    for i, r in enumerate(radii):
        for j, y in enumerate(years):
            x = piv[(piv['radius_km'] == r) & (piv['year'] == y)]
            if not x.empty:
                mat[i, j] = float(x['diff'].iloc[0])

    fig, ax = plt.subplots(figsize=(10.2, 3.8), constrained_layout=True)
    vmax = np.nanmax(np.abs(mat)) if np.isfinite(mat).any() else 1.0
    im = ax.imshow(mat, cmap='RdBu_r', aspect='auto', vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(years)))
    ax.set_xticklabels(years)
    ax.set_yticks(np.arange(len(radii)))
    ax.set_yticklabels([f'{int(r)} km' for r in radii])
    ax.set_xlabel('Year')
    ax.set_ylabel('Radius')
    ax.set_title('Matched - All Mean AGB Difference (Mg/ha)')

    for i in range(len(radii)):
        for j in range(len(years)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f'{mat[i, j]:.1f}', ha='center', va='center', fontsize=8, color='black')

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cbar.set_label('Difference in mean AGB (Mg/ha)')
    fig.savefig(out_png, bbox_inches='tight')
    fig.savefig(out_pdf, bbox_inches='tight')
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run comprehensive AGB temporal analysis for all vs matched mills.')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output-dir', type=Path, default=None)
    parser.add_argument('--limit', type=int, default=None, help='Optional debug row limit')
    args = parser.parse_args()

    cfg = load_config(args.config.resolve())
    matched_ids = load_matched_ids(cfg.matched_mills_csv)

    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_dir = (args.output_dir.resolve() if args.output_dir else (cfg.output_root / f'run_{ts}').resolve())
    plots_dir = run_dir / 'plots'
    run_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    print('Starting AGB extraction...', flush=True)
    df, year_files = extract_all_stats(cfg, limit=args.limit)
    df = df.sort_values(['mill_id', 'radius_km', 'year']).reset_index(drop=True)

    # Grouped view for all-vs-matched comparisons
    all_df = df.copy()
    all_df['group'] = 'ALL_MILLS'
    matched_df = df[df['mill_id'].isin(matched_ids)].copy()
    matched_df['group'] = 'MATCHED_H2_2024'
    grouped = pd.concat([all_df, matched_df], ignore_index=True)

    metrics_for_summary = ['agb_mean_mg_ha', 'agb_total_biomass_mg', 'valid_area_pct_of_shed']
    summary_long = pd.concat([summarize_metric(grouped, m) for m in metrics_for_summary], ignore_index=True)

    comparison = summary_long.pivot_table(
        index=['radius_km', 'year', 'metric'],
        columns='group',
        values=['mean', 'median', 'n_non_null', 'ci95'],
        aggfunc='first',
    )
    comparison.columns = [f'{a}_{b}' for a, b in comparison.columns]
    comparison = comparison.reset_index()
    comparison['mean_abs_diff_matched_minus_all'] = comparison['mean_MATCHED_H2_2024'] - comparison['mean_ALL_MILLS']
    comparison['mean_pct_diff_matched_vs_all'] = np.where(
        comparison['mean_ALL_MILLS'].abs() > 0,
        (comparison['mean_MATCHED_H2_2024'] - comparison['mean_ALL_MILLS']) / comparison['mean_ALL_MILLS'] * 100.0,
        np.nan,
    )

    change_df = compute_per_mill_change(df, cfg.year_start, cfg.year_end)
    change_with_group = change_df.copy()
    change_with_group['group'] = np.where(change_with_group['mill_id'].isin(matched_ids), 'MATCHED_H2_2024', 'ALL_MILLS')
    change_summary = summarize_change_by_group(change_df, matched_ids)

    audit = {
        'output_unique_mills': int(df['mill_id'].nunique()),
        'matched_unique_mills': int(len(matched_ids)),
        'matched_mills_found_in_outputs': int(len(set(df['mill_id'].unique()) & matched_ids)),
        'matched_mills_missing_in_outputs': int(len(matched_ids - set(df['mill_id'].unique()))),
        'years_processed': sorted(int(y) for y in year_files.keys()),
        'radii_km': [float(r) for r in cfg.radii_km],
        'rows_total': int(len(df)),
    }

    # Save tables
    df.to_csv(run_dir / 'agb_mill_year_stats.csv', index=False)
    summary_long.to_csv(run_dir / 'agb_summary_long.csv', index=False)
    comparison.to_csv(run_dir / 'agb_comparison_all_vs_matched.csv', index=False)
    change_df.to_csv(run_dir / 'agb_per_mill_change_2015_2022.csv', index=False)
    change_summary.to_csv(run_dir / 'agb_change_summary_all_vs_matched.csv', index=False)
    with open(run_dir / 'match_audit.json', 'w', encoding='utf-8') as f:
        json.dump(audit, f, indent=2)
    pd.DataFrame({'missing_mill_id': sorted(list(matched_ids - set(df['mill_id'].unique())))}).to_csv(
        run_dir / 'matched_mills_missing_in_outputs.csv', index=False
    )

    # Plots
    plot_temporal_trends(
        summary_long,
        plots_dir / 'fig_agb_temporal_trends.png',
        plots_dir / 'fig_agb_temporal_trends.pdf',
    )
    plot_change_boxplots(
        change_with_group,
        plots_dir / 'fig_agb_change_distributions.png',
        plots_dir / 'fig_agb_change_distributions.pdf',
    )
    plot_matched_minus_all_heatmap(
        summary_long,
        plots_dir / 'fig_agb_matched_minus_all_heatmap.png',
        plots_dir / 'fig_agb_matched_minus_all_heatmap.pdf',
    )

    # concise markdown summary
    focus = comparison[
        (comparison['metric'] == 'agb_mean_mg_ha') &
        (comparison['year'].isin([cfg.year_start, cfg.year_end]))
    ].copy()

    lines = [
        '# AGB Analysis Summary',
        '',
        f'- Years: {cfg.year_start}-{cfg.year_end}',
        f'- Radii: {", ".join(str(int(r)) for r in cfg.radii_km)} km',
        f"- Mills in output: {audit['output_unique_mills']}",
        f"- Matched mills found: {audit['matched_mills_found_in_outputs']} / {audit['matched_unique_mills']}",
        '',
        '## Mean AGB (Mg/ha): Matched vs All (selected years)',
        '',
        '| Radius (km) | Year | All mills | Matched | Diff (matched-all) | % diff |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for _, r in focus.sort_values(['radius_km', 'year']).iterrows():
        lines.append(
            f"| {int(r['radius_km'])} | {int(r['year'])} | {r['mean_ALL_MILLS']:.3f} | {r['mean_MATCHED_H2_2024']:.3f} | {r['mean_abs_diff_matched_minus_all']:.3f} | {r['mean_pct_diff_matched_vs_all']:.2f}% |"
        )

    (run_dir / 'analysis_summary.md').write_text('\n'.join(lines), encoding='utf-8')

    print(f'Run directory: {run_dir}', flush=True)
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == '__main__':
    main()
