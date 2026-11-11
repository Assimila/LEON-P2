#!/usr/bin/env python3
"""Compare fire incidence metrics for all mills vs five company-specific matched mill sets."""
from __future__ import annotations
import os

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

KEY_METRICS = [
    "burned_area_ha",
    "burned_pct_of_supply_shed",
    "burned_pct_of_valid_area",
]

METRIC_LABELS = {
    "burned_pixels": "Burned Pixels",
    "burned_area_ha": "Burned Area (ha)",
    "burned_pct_of_supply_shed": "Burned % of Supply Shed",
    "burned_pct_of_valid_area": "Burned % of Valid Area",
}

FREQ_METRICS = [
    "fire_frequency",
    "fire_frequency_pct",
    "mean_burned_pct_of_supply_shed",
    "max_burned_pct_of_supply_shed",
    "burned_area_trend_slope_ha_per_year",
    "burned_pct_trend_slope_per_year",
]

FREQ_METRIC_LABELS = {
    "fire_frequency": "Fire Frequency (years)",
    "fire_frequency_pct": "Fire Frequency (%)",
    "mean_burned_pct_of_supply_shed": "Mean Burned % of Supply Shed",
    "max_burned_pct_of_supply_shed": "Max Burned % of Supply Shed",
    "burned_area_trend_slope_ha_per_year": "Burned Area Trend (ha/yr)",
    "burned_pct_trend_slope_per_year": "Burned % Trend (/yr)",
}

COMPANY_COLORS = {
    "danone": "#E69F00",
    "ferrero": "#8C564B",
    "nestle": "#009E73",
    "pepsico": "#CC79A7",
    "wilmar": "#D55E00",
}
ALL_MILLS_COLOR = "#0072B2"


# ---------------------------------------------------------------------------
# Company specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompanySpec:
    key: str
    label: str
    matched_csvs: tuple[Path, ...]


# Repository root (override with the LEON_P2_ROOT environment variable).
PROJECT_ROOT = Path(os.environ.get("LEON_P2_ROOT", Path(__file__).resolve().parents[3]))


def default_company_specs() -> list[CompanySpec]:
    company_results = PROJECT_ROOT / "company" / "results"
    return [
        CompanySpec(
            key="danone",
            label="Danone",
            matched_csvs=(
                company_results / "danone" / "uml" / "matched_mills_mill-and-plantation-list-h2-2024.csv",
            ),
        ),
        CompanySpec(
            key="ferrero",
            label="Ferrero",
            matched_csvs=(
                company_results / "ferrero" / "uml" / "matched_mills_ferrero_core_palm-oil-mill-list-july-december-2022.csv",
                company_results / "ferrero" / "uml" / "matched_mills_acquired_brands_palm-oil-mill-list-july-december-2022.csv",
            ),
        ),
        CompanySpec(
            key="nestle",
            label="Nestle",
            matched_csvs=(
                company_results / "nestle" / "uml" / "unique_mills_responsible-sourcing-disclosure-palm-oil.csv",
            ),
        ),
        CompanySpec(
            key="pepsico",
            label="PepsiCo",
            matched_csvs=(
                company_results / "pepsico" / "uml" / "matched_mills_2024-global-palm-oil-mill-list.csv",
            ),
        ),
        CompanySpec(
            key="wilmar",
            label="Wilmar",
            matched_csvs=(
                company_results / "wilmar" / "uml" / "matched_mills_wilmar-own-mill_wilmar-sustainability-241231.csv",
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _read_csv_fallback(path: Path) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Failed to read CSV {path}: {last}")


def _standardize_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = out.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    return out


def _extract_mill_ids(df: pd.DataFrame) -> pd.Series:
    for cand in ("mill_id", "uml_id", "id"):
        if cand in df.columns:
            return df[cand].astype(str).str.strip()
    raise ValueError("No mill id column found. Expected one of: mill_id, uml_id, id")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare fire metrics for all mills vs matched company mill sets."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run directory containing fire_mill_year_stats.csv and fire_frequency_per_mill.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: <run-dir>/analysis_companies)",
    )
    return parser.parse_args()


def load_fire_outputs(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    yearly = pd.read_csv(run_dir / "fire_mill_year_stats.csv")
    yearly = _standardize_cols(yearly)
    yearly["mill_id"] = yearly["mill_id"].astype(str).str.strip()

    freq = pd.read_csv(run_dir / "fire_frequency_per_mill.csv")
    freq = _standardize_cols(freq)
    freq["mill_id"] = freq["mill_id"].astype(str).str.strip()

    return yearly, freq


def load_company_ids(spec: CompanySpec) -> tuple[pd.DataFrame, set[str]]:
    frames = []
    for path in spec.matched_csvs:
        df = _standardize_cols(_read_csv_fallback(path))
        df["mill_id"] = _extract_mill_ids(df)
        df["_source_csv"] = str(path)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    ids = set(combined["mill_id"].astype(str).str.strip().unique())
    return combined, ids


# ---------------------------------------------------------------------------
# Audit & grouping
# ---------------------------------------------------------------------------

def make_match_audit(all_df: pd.DataFrame, matched_df: pd.DataFrame, matched_ids: set[str]) -> dict:
    all_ids = set(all_df["mill_id"].unique())
    missing_in_outputs = sorted(matched_ids - all_ids)
    return {
        "output_unique_mills": len(all_ids),
        "matched_source_rows": int(len(matched_df)),
        "matched_unique_mills": len(matched_ids),
        "matched_mills_found_in_outputs": len(matched_ids & all_ids),
        "matched_mills_missing_in_outputs": len(missing_in_outputs),
        "matched_mills_missing_share_pct": (
            len(missing_in_outputs) / len(matched_ids) * 100.0 if matched_ids else 0.0
        ),
        "source_csvs": sorted(str(p) for p in matched_df["_source_csv"].unique()),
    }


def make_grouped_df(all_df: pd.DataFrame, matched_ids: set[str], company_group: str) -> pd.DataFrame:
    all_tag = all_df.copy()
    all_tag["group"] = "ALL_MILLS"
    matched_tag = all_df[all_df["mill_id"].isin(matched_ids)].copy()
    matched_tag["group"] = company_group
    return pd.concat([all_tag, matched_tag], ignore_index=True)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def summarize_yearly_metrics(grouped: pd.DataFrame, metrics: Iterable[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for (radius, year, group), sub in grouped.groupby(["radius_km", "year", "group"], sort=True):
        for metric in metrics:
            s = pd.to_numeric(sub[metric], errors="coerce").dropna()
            n = int(len(s))
            std = float(s.std(ddof=1)) if n > 1 else np.nan
            se = std / np.sqrt(n) if n > 1 else np.nan
            ci95 = 1.96 * se if n > 1 else np.nan
            rows.append({
                "radius_km": float(radius),
                "year": int(year),
                "group": group,
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "n_non_null": n,
                "mean": float(s.mean()) if n else np.nan,
                "median": float(s.median()) if n else np.nan,
                "std": std,
                "min": float(s.min()) if n else np.nan,
                "p25": float(s.quantile(0.25)) if n else np.nan,
                "p75": float(s.quantile(0.75)) if n else np.nan,
                "max": float(s.max()) if n else np.nan,
                "ci95": ci95,
            })
    return pd.DataFrame(rows)


def summarize_freq_metrics(grouped_freq: pd.DataFrame, metrics: Iterable[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for (radius, group), sub in grouped_freq.groupby(["radius_km", "group"], sort=True):
        for metric in metrics:
            s = pd.to_numeric(sub[metric], errors="coerce").dropna()
            n = int(len(s))
            std = float(s.std(ddof=1)) if n > 1 else np.nan
            se = std / np.sqrt(n) if n > 1 else np.nan
            ci95 = 1.96 * se if n > 1 else np.nan
            rows.append({
                "radius_km": float(radius),
                "group": group,
                "metric": metric,
                "metric_label": FREQ_METRIC_LABELS.get(metric, metric),
                "n_non_null": n,
                "mean": float(s.mean()) if n else np.nan,
                "median": float(s.median()) if n else np.nan,
                "std": std,
                "ci95": ci95,
            })
    return pd.DataFrame(rows)


def make_yearly_comparison_table(summary: pd.DataFrame, company_group: str, company_key: str, company_label: str) -> pd.DataFrame:
    piv = summary.pivot_table(
        index=["radius_km", "year", "metric", "metric_label"],
        columns="group",
        values=["mean", "median", "ci95", "n_non_null"],
        aggfunc="first",
    )
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    out = piv.reset_index()
    company_mean_col = f"mean_{company_group}"
    if company_mean_col not in out.columns:
        out[company_mean_col] = np.nan
        out[f"median_{company_group}"] = np.nan
        out[f"ci95_{company_group}"] = np.nan
        out[f"n_non_null_{company_group}"] = 0
    out["mean_abs_diff_company_minus_all"] = out[company_mean_col] - out["mean_ALL_MILLS"]
    out["mean_pct_diff_company_vs_all"] = np.where(
        out["mean_ALL_MILLS"].abs() > 0,
        (out[company_mean_col] - out["mean_ALL_MILLS"]) / out["mean_ALL_MILLS"] * 100.0,
        np.nan,
    )
    out["company_key"] = company_key
    out["company_label"] = company_label
    return out.sort_values(["radius_km", "year", "metric"]).reset_index(drop=True)


def make_freq_comparison_table(freq_summary: pd.DataFrame, company_group: str, company_key: str, company_label: str) -> pd.DataFrame:
    piv = freq_summary.pivot_table(
        index=["radius_km", "metric", "metric_label"],
        columns="group",
        values=["mean", "median", "ci95", "n_non_null"],
        aggfunc="first",
    )
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    out = piv.reset_index()
    company_mean_col = f"mean_{company_group}"
    if company_mean_col not in out.columns:
        out[company_mean_col] = np.nan
        out[f"median_{company_group}"] = np.nan
        out[f"ci95_{company_group}"] = np.nan
        out[f"n_non_null_{company_group}"] = 0
    out["mean_abs_diff_company_minus_all"] = out[company_mean_col] - out["mean_ALL_MILLS"]
    out["mean_pct_diff_company_vs_all"] = np.where(
        out["mean_ALL_MILLS"].abs() > 0,
        (out[company_mean_col] - out["mean_ALL_MILLS"]) / out["mean_ALL_MILLS"] * 100.0,
        np.nan,
    )
    out["company_key"] = company_key
    out["company_label"] = company_label
    return out.sort_values(["radius_km", "metric"]).reset_index(drop=True)


def summarize_coverage(grouped: pd.DataFrame) -> pd.DataFrame:
    cov = (
        grouped.groupby(["radius_km", "group", "coverage_status"], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )
    total = cov.groupby(["radius_km", "group"])["count"].transform("sum")
    cov["share_pct"] = cov["count"] / total * 100.0
    return cov.sort_values(["radius_km", "group", "coverage_status"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def set_plot_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "font.family": "DejaVu Sans",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.9,
        "axes.grid": False,
        "legend.frameon": False,
    })


def _style_axis(ax: plt.Axes) -> None:
    ax.set_axisbelow(True)
    ax.grid(False)
    ax.spines["left"].set_color("#4a4a4a")
    ax.spines["bottom"].set_color("#4a4a4a")


def plot_temporal_trends(summary: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    metric = "burned_pct_of_supply_shed"
    company_color = COMPANY_COLORS[company_key]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5), constrained_layout=True)

    for ax, radius in zip(axes, [25.0, 50.0]):
        sub = summary[(summary["radius_km"] == radius) & (summary["metric"] == metric)]
        # Draw CI bands first, then ALL_MILLS line, then company line on top
        line_styles = {
            "ALL_MILLS": {"linewidth": 2.0, "linestyle": "-", "markersize": 4.5, "zorder": 3},
            company_group: {"linewidth": 2.2, "linestyle": "--", "markersize": 5, "zorder": 4},
        }
        groups = [
            ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
            (company_group, company_color, company_label),
        ]
        for group, color, _ in groups:
            g = sub[sub["group"] == group].sort_values("year")
            if g.empty:
                continue
            x = g["year"].to_numpy()
            y = g["mean"].to_numpy(dtype=float)
            ci = g["ci95"].to_numpy(dtype=float)
            ci_valid = np.isfinite(ci)
            if ci_valid.any():
                ax.fill_between(x, y - np.where(ci_valid, ci, 0), y + np.where(ci_valid, ci, 0), alpha=0.10, color=color, zorder=1)
        for group, color, label in groups:
            g = sub[sub["group"] == group].sort_values("year")
            if g.empty:
                continue
            x = g["year"].to_numpy()
            y = g["mean"].to_numpy(dtype=float)
            ls = line_styles.get(group, {})
            lw = ls.get("linewidth", 2.0)
            zo = ls.get("zorder", 3)
            lstyle = ls.get("linestyle", "-")
            ms = ls.get("markersize", 4.2)
            # White halo so line is visible over any CI band
            ax.plot(x, y, marker="o", color="white", linewidth=lw + 2.5,
                    linestyle=lstyle, markersize=ms + 2, zorder=zo - 0.5)
            ax.plot(x, y, marker="o", color=color, label=label,
                    linewidth=lw, linestyle=lstyle, markersize=ms, zorder=zo)

        ax.set_title(f"Mean Burned % of Supply Shed | {int(radius)} km")
        ax.set_xlabel("Year")
        ax.set_ylabel("Burned %")
        ax.set_xticks(sorted(sub["year"].unique()))
        ax.tick_params(axis="x", rotation=45)
        _style_axis(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(f"Fire Trends: All Mills vs {company_label}", fontsize=14, y=1.05)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


def plot_fire_frequency_box(grouped_freq: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), constrained_layout=True)

    plot_metrics = [
        ("fire_frequency", "Fire Frequency (years)"),
        ("mean_burned_pct_of_supply_shed", "Mean Annual Burned %"),
    ]

    for ax, (metric, title) in zip(axes, plot_metrics):
        data = []
        labels = []
        colors = []
        for radius in [25.0, 50.0]:
            for group, color, label in [
                ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
                (company_group, COMPANY_COLORS[company_key], company_label),
            ]:
                sub = grouped_freq[
                    (grouped_freq["radius_km"] == radius) & (grouped_freq["group"] == group)
                ][metric].dropna()
                data.append(sub.to_numpy())
                labels.append(f"{int(radius)}km\n{label}")
                colors.append(color)

        bp = ax.boxplot(
            data,
            patch_artist=True,
            tick_labels=labels,
            widths=0.58,
            showfliers=False,
            whiskerprops={"color": "#4a4a4a", "linewidth": 0.9},
            capprops={"color": "#4a4a4a", "linewidth": 0.9},
            boxprops={"edgecolor": "#4a4a4a", "linewidth": 0.9},
            medianprops={"color": "#1a1a1a", "linewidth": 1.2},
        )
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)

        ax.set_title(title)
        ax.set_ylabel("Value")
        _style_axis(ax)

    fig.suptitle(f"Fire Frequency: All Mills vs {company_label}", fontsize=14)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


def plot_coverage_stacked(coverage: pd.DataFrame, company_group: str, company_label: str, out_png: Path, out_pdf: Path) -> None:
    set_plot_style()
    fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)

    order = [
        (25.0, "ALL_MILLS", "All Mills"),
        (25.0, company_group, company_label),
        (50.0, "ALL_MILLS", "All Mills"),
        (50.0, company_group, company_label),
    ]
    labels = [f"{int(r)}km\n{label}" for r, _, label in order]
    x = np.arange(len(order))

    status_colors = {
        "FULL_COVERAGE": "#2A9D8F",
        "PARTIAL_COVERAGE": "#F4A261",
        "NO_COVERAGE": "#6D597A",
    }
    bottoms = np.zeros(len(order))

    for status in ["FULL_COVERAGE", "PARTIAL_COVERAGE", "NO_COVERAGE"]:
        vals = []
        for radius, group, _ in order:
            s = coverage[
                (coverage["radius_km"] == radius)
                & (coverage["group"] == group)
                & (coverage["coverage_status"] == status)
            ]
            vals.append(float(s["share_pct"].iloc[0]) if not s.empty else 0.0)

        ax.bar(x, vals, bottom=bottoms, width=0.56, color=status_colors[status],
               label=status.replace("_", " "), edgecolor="white", linewidth=0.7)
        bottoms += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Share of Mills (%)")
    ax.set_title(f"Coverage Status: All Mills vs {company_label}")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right")
    _style_axis(ax)

    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


def plot_company_diff_heatmap(overview: pd.DataFrame, out_png: Path, out_pdf: Path) -> None:
    """Heatmap: company vs all mills % diff for fire frequency metrics across companies."""
    set_plot_style()
    metrics = ["fire_frequency", "mean_burned_pct_of_supply_shed", "max_burned_pct_of_supply_shed"]
    columns = [(25.0, m) for m in metrics] + [(50.0, m) for m in metrics]
    companies = list(dict.fromkeys(overview["company_label"]))

    mat = np.full((len(companies), len(columns)), np.nan)
    for i, company in enumerate(companies):
        for j, (radius, metric) in enumerate(columns):
            sub = overview[
                (overview["company_label"] == company)
                & (overview["radius_km"] == radius)
                & (overview["metric"] == metric)
            ]
            if not sub.empty:
                mat[i, j] = float(sub["mean_pct_diff_company_vs_all"].iloc[0])

    fig, ax = plt.subplots(figsize=(11.5, 4.8), constrained_layout=True)
    vmax = np.nanmax(np.abs(mat)) if np.isfinite(mat).any() else 1.0
    im = ax.imshow(mat, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels([
        f"{int(r)}km\n{FREQ_METRIC_LABELS.get(m, m).replace(' of Supply Shed', '')}"
        for r, m in columns
    ])
    ax.set_yticks(np.arange(len(companies)))
    ax.set_yticklabels(companies)
    ax.set_title("Company vs All Mills: Mean % Difference (Fire Frequency Metrics)")

    for i in range(len(companies)):
        for j in range(len(columns)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center", fontsize=8, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cbar.set_label("% difference vs all mills")
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Per-company pipeline
# ---------------------------------------------------------------------------

def save_company_outputs(
    out_dir: Path,
    match_audit: dict,
    missing_ids: list[str],
    yearly_summary: pd.DataFrame,
    yearly_comparison: pd.DataFrame,
    freq_summary: pd.DataFrame,
    freq_comparison: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "match_audit.json", "w", encoding="utf-8") as f:
        json.dump(match_audit, f, indent=2)

    pd.DataFrame({"missing_mill_id": missing_ids}).to_csv(
        out_dir / "matched_mills_missing_in_outputs.csv", index=False
    )

    yearly_summary.to_csv(out_dir / "yearly_summary_stats_long.csv", index=False)
    yearly_comparison.to_csv(out_dir / "yearly_comparison_key_stats.csv", index=False)
    freq_summary.to_csv(out_dir / "freq_summary_stats.csv", index=False)
    freq_comparison.to_csv(out_dir / "freq_comparison_key_stats.csv", index=False)
    coverage.to_csv(out_dir / "coverage_status_summary.csv", index=False)


def write_company_summary_md(
    out_dir: Path,
    company_label: str,
    company_group: str,
    match_audit: dict,
    freq_comparison: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    focus = freq_comparison[freq_comparison["metric"].isin(FREQ_METRICS)].copy()
    focus = focus.sort_values(["radius_km", "metric"])

    coverage_piv = coverage.pivot_table(
        index=["radius_km", "group"],
        columns="coverage_status",
        values="share_pct",
        aggfunc="first",
    ).reset_index().fillna(0.0)

    company_mean_col = f"mean_{company_group}"

    lines = [
        f"# All Mills vs {company_label} — Fire Incidence",
        "",
        "## Match Audit",
        f"- Output unique mills: {match_audit['output_unique_mills']}",
        f"- Matched source rows: {match_audit['matched_source_rows']}",
        f"- Matched unique mills: {match_audit['matched_unique_mills']}",
        f"- Matched mills found in outputs: {match_audit['matched_mills_found_in_outputs']}",
        f"- Matched mills missing in outputs: {match_audit['matched_mills_missing_in_outputs']}",
        "",
        "## Fire Frequency: Key Mean Comparison",
        "",
        "| Radius (km) | Metric | All mills mean | Company mean | Abs diff | % diff |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for _, row in focus.iterrows():
        company_mean = row.get(company_mean_col, np.nan)
        cm_str = f"{company_mean:.4f}" if pd.notna(company_mean) else "N/A"
        ad_str = f"{row['mean_abs_diff_company_minus_all']:.4f}" if pd.notna(row['mean_abs_diff_company_minus_all']) else "N/A"
        pd_str = f"{row['mean_pct_diff_company_vs_all']:.2f}%" if pd.notna(row['mean_pct_diff_company_vs_all']) else "N/A"
        lines.append(
            f"| {int(row['radius_km'])} | {row['metric']} | {row['mean_ALL_MILLS']:.4f} | {cm_str} | {ad_str} | {pd_str} |"
        )

    lines.extend([
        "",
        "## Coverage Summary (%)",
        "",
        "| Radius (km) | Group | FULL | PARTIAL | NONE |",
        "|---:|---|---:|---:|---:|",
    ])
    for _, row in coverage_piv.sort_values(["radius_km", "group"]).iterrows():
        lines.append(
            f"| {int(row['radius_km'])} | {row['group']} | {row.get('FULL_COVERAGE', 0.0):.2f}% | {row.get('PARTIAL_COVERAGE', 0.0):.2f}% | {row.get('NO_COVERAGE', 0.0):.2f}% |"
        )

    (out_dir / "analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_company_analysis(yearly_df: pd.DataFrame, freq_df: pd.DataFrame, spec: CompanySpec, out_dir: Path) -> dict:
    matched_df, matched_ids = load_company_ids(spec)
    company_group = spec.label.upper().replace(" ", "_")

    # Yearly grouped
    grouped_yearly = make_grouped_df(yearly_df, matched_ids, company_group)
    yearly_summary = summarize_yearly_metrics(grouped_yearly, KEY_METRICS)
    yearly_comparison = make_yearly_comparison_table(yearly_summary, company_group, spec.key, spec.label)

    # Frequency grouped
    grouped_freq = make_grouped_df(freq_df, matched_ids, company_group)
    freq_summary = summarize_freq_metrics(grouped_freq, FREQ_METRICS)
    freq_comparison = make_freq_comparison_table(freq_summary, company_group, spec.key, spec.label)

    # Coverage (deduplicate yearly to one row per mill-radius for coverage)
    coverage_base = yearly_df.drop_duplicates(subset=["mill_id", "radius_km"])[["mill_id", "radius_km", "coverage_status"]]
    coverage_grouped = make_grouped_df(coverage_base, matched_ids, company_group)
    coverage = summarize_coverage(coverage_grouped)

    audit = make_match_audit(yearly_df, matched_df, matched_ids)
    missing_ids = sorted(list(matched_ids - set(yearly_df["mill_id"].unique())))

    save_company_outputs(out_dir, audit, missing_ids, yearly_summary, yearly_comparison, freq_summary, freq_comparison, coverage)

    # Plots
    plot_temporal_trends(yearly_summary, company_group, spec.label, spec.key,
                         out_dir / "fig_fire_temporal_trends.png", out_dir / "fig_fire_temporal_trends.pdf")
    plot_fire_frequency_box(grouped_freq, company_group, spec.label, spec.key,
                            out_dir / "fig_fire_frequency_boxplot.png", out_dir / "fig_fire_frequency_boxplot.pdf")
    plot_coverage_stacked(coverage, company_group, spec.label,
                          out_dir / "fig_coverage_composition.png", out_dir / "fig_coverage_composition.pdf")

    write_company_summary_md(out_dir, spec.label, company_group, audit, freq_comparison, coverage)

    return {
        "freq_overview": freq_comparison,
        "audit": audit,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = (args.out_dir.resolve() if args.out_dir else run_dir / "analysis_companies")
    out_dir.mkdir(parents=True, exist_ok=True)

    yearly_df, freq_df = load_fire_outputs(run_dir)

    specs = default_company_specs()
    manifest_rows = []
    overview_frames = []

    for spec in specs:
        print(f"Processing {spec.label}...", flush=True)
        company_out_dir = out_dir / spec.key
        result = run_company_analysis(yearly_df, freq_df, spec, company_out_dir)
        overview_frames.append(result["freq_overview"])
        manifest_rows.append({
            "company_key": spec.key,
            "company_label": spec.label,
            "source_csv_count": len(spec.matched_csvs),
            "source_csvs": "; ".join(str(p) for p in spec.matched_csvs),
            **result["audit"],
        })

    overview = pd.concat(overview_frames, ignore_index=True)
    overview.to_csv(out_dir / "company_overview_key_stats.csv", index=False)
    pd.DataFrame(manifest_rows).to_csv(out_dir / "company_manifest.csv", index=False)
    with open(out_dir / "company_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_rows, f, indent=2)

    plot_company_diff_heatmap(overview, out_dir / "fig_company_diff_heatmap.png", out_dir / "fig_company_diff_heatmap.pdf")

    print(f"\nSaved company analyses to: {out_dir}")
    print(pd.DataFrame(manifest_rows)[["company_label", "matched_unique_mills", "matched_mills_found_in_outputs"]].to_string(index=False))


if __name__ == "__main__":
    main()
