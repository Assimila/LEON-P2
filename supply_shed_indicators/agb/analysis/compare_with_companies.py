#!/usr/bin/env python3
from __future__ import annotations
import os

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


AGB_METRICS = [
    "agb_mean_mg_ha",
    "agb_total_biomass_mg",
    "valid_area_pct_of_shed",
]

KEY_METRICS = [
    "agb_mean_mg_ha",
    "agb_total_biomass_mg",
]

CHANGE_METRICS = [
    "agb_delta_end_minus_start_mg_ha",
    "agb_pct_change_end_vs_start",
    "agb_cagr_pct",
    "agb_trend_slope_mg_ha_per_year",
]

METRIC_LABELS = {
    "agb_mean_mg_ha": "Mean AGB (Mg/ha)",
    "agb_total_biomass_mg": "Total AGB in Supply Shed (Mg)",
    "valid_area_pct_of_shed": "Valid AGB Coverage (% of supply shed)",
    "agb_delta_end_minus_start_mg_ha": "AGB Change (Mg/ha)",
    "agb_pct_change_end_vs_start": "AGB % Change",
    "agb_cagr_pct": "AGB CAGR (%)",
    "agb_trend_slope_mg_ha_per_year": "AGB Trend Slope (Mg/ha/year)",
}

COMPANY_COLORS = {
    "danone": "#E69F00",
    "ferrero": "#8C564B",
    "nestle": "#009E73",
    "pepsico": "#CC79A7",
    "wilmar": "#D55E00",
}
ALL_MILLS_COLOR = "#0072B2"


@dataclass(frozen=True)
class CompanySpec:
    key: str
    label: str
    matched_csvs: tuple[Path, ...]


# Repository root (override with the LEON_P2_ROOT environment variable).
PROJECT_ROOT = Path(os.environ.get("LEON_P2_ROOT", Path(__file__).resolve().parents[3]))


def _latest_run(outputs_dir: Path) -> Path | None:
    """Return the most recent run_* directory under outputs_dir, if any."""
    runs = sorted(p for p in outputs_dir.glob("run_*") if p.is_dir())
    return runs[-1] if runs else None

DEFAULT_RUN_DIR = _latest_run(PROJECT_ROOT / "supply_shed_indicators" / "agb" / "outputs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare AGB metrics for all mills vs matched company mill sets."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        required=DEFAULT_RUN_DIR is None,
        help="Run directory containing AGB outputs",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: <run-dir>/analysis_companies)",
    )
    parser.add_argument(
        "--year-start",
        type=int,
        default=2015,
    )
    parser.add_argument(
        "--year-end",
        type=int,
        default=2022,
    )
    return parser.parse_args()


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


def load_agb_outputs(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "agb_mill_year_stats.csv"
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    df["mill_id"] = df["mill_id"].astype(str).str.strip()
    return df


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


def make_match_audit(all_df: pd.DataFrame, matched_df: pd.DataFrame, matched_ids: set[str]) -> dict:
    all_ids = set(all_df["mill_id"].unique())
    missing_in_outputs = sorted(matched_ids - all_ids)
    present_in_outputs = sorted(matched_ids & all_ids)
    return {
        "output_unique_mills": len(all_ids),
        "matched_source_rows": int(len(matched_df)),
        "matched_unique_mills": len(matched_ids),
        "matched_mills_found_in_outputs": len(present_in_outputs),
        "matched_mills_missing_in_outputs": len(missing_in_outputs),
        "matched_mills_missing_share_pct": (
            len(missing_in_outputs) / len(matched_ids) * 100.0 if matched_ids else 0.0
        ),
        "source_csvs": sorted(str(path) for path in matched_df["_source_csv"].unique()),
    }


def make_grouped_df(all_df: pd.DataFrame, matched_ids: set[str], company_group: str) -> pd.DataFrame:
    all_tag = all_df.copy()
    all_tag["group"] = "ALL_MILLS"
    matched_tag = all_df[all_df["mill_id"].isin(matched_ids)].copy()
    matched_tag["group"] = company_group
    return pd.concat([all_tag, matched_tag], ignore_index=True)


def summarize_metrics(grouped: pd.DataFrame, metrics: Iterable[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for (radius, year, group), sub in grouped.groupby(["radius_km", "year", "group"], sort=True):
        for metric in metrics:
            if metric not in sub.columns:
                continue
            s = pd.to_numeric(sub[metric], errors="coerce").dropna()
            n = int(s.shape[0])
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


def make_comparison_table(summary: pd.DataFrame, company_group: str, company_key: str, company_label: str) -> pd.DataFrame:
    piv = summary.pivot_table(
        index=["radius_km", "year", "metric", "metric_label"],
        columns="group",
        values=["mean", "median", "ci95", "n_non_null"],
        aggfunc="first",
    )
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    out = piv.reset_index()

    out["mean_abs_diff_company_minus_all"] = out[f"mean_{company_group}"] - out["mean_ALL_MILLS"]
    out["mean_pct_diff_company_vs_all"] = np.where(
        out["mean_ALL_MILLS"].abs() > 0,
        (out[f"mean_{company_group}"] - out["mean_ALL_MILLS"]) / out["mean_ALL_MILLS"] * 100.0,
        np.nan,
    )
    out["company_key"] = company_key
    out["company_label"] = company_label
    return out.sort_values(["radius_km", "year", "metric"]).reset_index(drop=True)


def compute_per_mill_change(df: pd.DataFrame, year_start: int, year_end: int) -> pd.DataFrame:
    all_keys = df[["mill_id", "radius_km"]].drop_duplicates().reset_index(drop=True)
    keep = ["mill_id", "radius_km", "year", "agb_mean_mg_ha"]
    x = df[keep].copy()
    p = x.pivot_table(index=["mill_id", "radius_km"], columns="year", values="agb_mean_mg_ha", aggfunc="first")
    p = p.reset_index()
    p = all_keys.merge(p, on=["mill_id", "radius_km"], how="left")
    p["agb_mean_start"] = p.get(year_start, np.nan)
    p["agb_mean_end"] = p.get(year_end, np.nan)
    p["agb_delta_end_minus_start_mg_ha"] = p["agb_mean_end"] - p["agb_mean_start"]
    p["agb_pct_change_end_vs_start"] = np.where(
        p["agb_mean_start"] > 0,
        (p["agb_mean_end"] - p["agb_mean_start"]) / p["agb_mean_start"] * 100.0,
        np.nan,
    )
    span = year_end - year_start
    p["agb_cagr_pct"] = np.where(
        (p["agb_mean_start"] > 0) & (p["agb_mean_end"] > 0) & (span > 0),
        ((p["agb_mean_end"] / p["agb_mean_start"]) ** (1.0 / span) - 1.0) * 100.0,
        np.nan,
    )

    slopes = []
    for (mill_id, radius), sub in df.groupby(["mill_id", "radius_km"]):
        y = sub[["year", "agb_mean_mg_ha"]].dropna().sort_values("year")
        if len(y) >= 2:
            slope = float(np.polyfit(y["year"].to_numpy(), y["agb_mean_mg_ha"].to_numpy(), 1)[0])
        else:
            slope = np.nan
        slopes.append({"mill_id": mill_id, "radius_km": radius, "agb_trend_slope_mg_ha_per_year": slope})
    slopes_df = pd.DataFrame(slopes)
    return p.merge(slopes_df, on=["mill_id", "radius_km"], how="left")


def summarize_change_by_group(change_df: pd.DataFrame, matched_ids: set[str], company_group: str) -> pd.DataFrame:
    base = change_df.copy()
    base["group"] = np.where(base["mill_id"].isin(matched_ids), company_group, "ALL_MILLS")

    rows: list[dict] = []
    for group_label in ["ALL_MILLS", company_group]:
        sub_group = base if group_label == "ALL_MILLS" else base[base["group"] == company_group]
        for radius, sub_r in sub_group.groupby("radius_km"):
            for metric in CHANGE_METRICS:
                if metric not in sub_r.columns:
                    continue
                s = pd.to_numeric(sub_r[metric], errors="coerce").dropna()
                n = int(len(s))
                rows.append({
                    "radius_km": float(radius),
                    "group": group_label,
                    "metric": metric,
                    "metric_label": METRIC_LABELS.get(metric, metric),
                    "n_non_null": n,
                    "mean": float(s.mean()) if n else np.nan,
                    "median": float(s.median()) if n else np.nan,
                    "std": float(s.std(ddof=1)) if n > 1 else np.nan,
                    "p25": float(s.quantile(0.25)) if n else np.nan,
                    "p75": float(s.quantile(0.75)) if n else np.nan,
                })
    return pd.DataFrame(rows)


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
        "xtick.major.size": 4.0,
        "ytick.major.size": 4.0,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "legend.frameon": False,
    })


def _style_axis(ax: plt.Axes) -> None:
    ax.set_axisbelow(True)
    ax.grid(False)
    ax.spines["left"].set_color("#4a4a4a")
    ax.spines["bottom"].set_color("#4a4a4a")


def plot_temporal_trends(summary: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_path: Path) -> None:
    set_plot_style()
    metrics = ["agb_mean_mg_ha", "agb_total_biomass_mg"]
    metric_titles = {
        "agb_mean_mg_ha": "Mean AGB (Mg/ha)",
        "agb_total_biomass_mg": "Total AGB in Supply Shed (Mg)",
    }
    company_color = COMPANY_COLORS[company_key]

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.8), constrained_layout=True)
    for r_idx, radius in enumerate([25.0, 50.0]):
        for m_idx, metric in enumerate(metrics):
            ax = axes[m_idx, r_idx]
            sub = summary[(summary["radius_km"] == radius) & (summary["metric"] == metric)]
            for group, color, label in [
                ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
                (company_group, company_color, company_label),
            ]:
                g = sub[sub["group"] == group].sort_values("year")
                if g.empty:
                    continue
                x = g["year"].to_numpy()
                y = g["mean"].to_numpy(dtype=float)
                ax.plot(x, y, marker="o", markersize=4.2, linewidth=2.0, color=color, label=label)

            ax.set_title(f"{metric_titles[metric]} | {int(radius)} km")
            ax.set_xlabel("Year")
            ax.set_ylabel("Value")
            ax.set_xticks(sorted(sub["year"].unique()))
            _style_axis(ax)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(f"Temporal AGB Trends: All Mills vs {company_label}", fontsize=15, y=1.03)
    for ext in (".png", ".pdf"):
        fig.savefig(out_path.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def plot_change_boxplots(change_with_group: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_path: Path) -> None:
    set_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), constrained_layout=True)
    company_color = COMPANY_COLORS[company_key]

    plot_metrics = [
        ("agb_delta_end_minus_start_mg_ha", "AGB Change (Mg/ha)"),
        ("agb_trend_slope_mg_ha_per_year", "AGB Trend Slope (Mg/ha/year)"),
    ]

    for ax, (metric, title) in zip(axes, plot_metrics):
        data = []
        labels = []
        colors = []
        for radius in [25.0, 50.0]:
            for group, color, label in [
                ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
                (company_group, company_color, company_label),
            ]:
                sub = change_with_group[
                    (change_with_group["radius_km"] == radius) & (change_with_group["group"] == group)
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
            patch.set_alpha(0.78)
        ax.set_title(title)
        _style_axis(ax)

    fig.suptitle(f"Per-mill AGB Change: All Mills vs {company_label}", fontsize=14)
    for ext in (".png", ".pdf"):
        fig.savefig(out_path.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def plot_company_diff_heatmap(overview: pd.DataFrame, out_path: Path) -> None:
    set_plot_style()
    metric = "agb_mean_mg_ha"
    companies = list(dict.fromkeys(overview["company_label"]))
    years = sorted(overview["year"].unique())
    columns = [(25.0, y) for y in years] + [(50.0, y) for y in years]

    mat = np.full((len(companies), len(columns)), np.nan)
    for i, company in enumerate(companies):
        for j, (radius, year) in enumerate(columns):
            sub = overview[
                (overview["company_label"] == company)
                & (overview["radius_km"] == radius)
                & (overview["metric"] == metric)
                & (overview["year"] == year)
            ]
            if not sub.empty:
                mat[i, j] = float(sub["mean_pct_diff_company_vs_all"].iloc[0])

    fig, ax = plt.subplots(figsize=(14, 4.8), constrained_layout=True)
    vmax = np.nanmax(np.abs(mat)) if np.isfinite(mat).any() else 1.0
    im = ax.imshow(mat, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels([f"{int(r)}km\n{int(y)}" for r, y in columns], fontsize=8)
    ax.set_yticks(np.arange(len(companies)))
    ax.set_yticklabels(companies)
    ax.set_title("Company vs All Mills: Mean AGB % Difference by Year")

    for i in range(len(companies)):
        for j in range(len(columns)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center", fontsize=7, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("% difference vs all mills")
    for ext in (".png", ".pdf"):
        fig.savefig(out_path.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def plot_company_change_summary(change_overview: pd.DataFrame, out_path: Path) -> None:
    set_plot_style()
    metric = "agb_trend_slope_mg_ha_per_year"
    companies = list(dict.fromkeys(change_overview["company_label"]))

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    for ax, radius in zip(axes, [25.0, 50.0]):
        all_val = change_overview[
            (change_overview["group"] == "ALL_MILLS")
            & (change_overview["radius_km"] == radius)
            & (change_overview["metric"] == metric)
        ]
        all_mean = float(all_val["mean"].iloc[0]) if not all_val.empty else np.nan

        comp_means = []
        comp_labels = []
        comp_colors = []
        for spec in default_company_specs():
            cg = spec.label.upper().replace(" ", "_")
            sub = change_overview[
                (change_overview["group"] == cg)
                & (change_overview["radius_km"] == radius)
                & (change_overview["metric"] == metric)
            ]
            if not sub.empty:
                comp_means.append(float(sub["mean"].iloc[0]))
                comp_labels.append(spec.label)
                comp_colors.append(COMPANY_COLORS[spec.key])

        x = np.arange(len(comp_labels))
        ax.bar(x, comp_means, color=comp_colors, edgecolor="white", linewidth=0.7, width=0.6)
        ax.axhline(all_mean, color=ALL_MILLS_COLOR, linewidth=1.5, linestyle="--", label="All Mills mean")
        ax.set_xticks(x)
        ax.set_xticklabels(comp_labels, rotation=30, ha="right")
        ax.set_title(f"AGB Trend Slope | {int(radius)} km")
        ax.set_ylabel("Mg/ha/year")
        ax.legend()
        _style_axis(ax)

    fig.suptitle("Mean AGB Trend Slope by Company", fontsize=14)
    for ext in (".png", ".pdf"):
        fig.savefig(out_path.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Per-company output
# ---------------------------------------------------------------------------

def save_company_outputs(
    out_dir: Path,
    match_audit: dict,
    missing_ids: list[str],
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    change_summary: pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "match_audit.json", "w", encoding="utf-8") as f:
        json.dump(match_audit, f, indent=2)
    pd.DataFrame({"missing_mill_id": missing_ids}).to_csv(
        out_dir / "matched_mills_missing_in_outputs.csv", index=False
    )
    summary.to_csv(out_dir / "agb_summary_stats_long.csv", index=False)
    comparison.to_csv(out_dir / "agb_comparison_key_stats.csv", index=False)
    change_summary.to_csv(out_dir / "agb_change_summary.csv", index=False)


def write_company_summary_md(
    out_dir: Path,
    company_label: str,
    company_group: str,
    match_audit: dict,
    comparison: pd.DataFrame,
    year_start: int,
    year_end: int,
) -> None:
    focus = comparison[
        (comparison["metric"] == "agb_mean_mg_ha")
        & (comparison["year"].isin([year_start, year_end]))
    ].copy().sort_values(["radius_km", "year"])

    lines = [
        f"# AGB Analysis: All Mills vs {company_label}",
        "",
        "## Match Audit",
        f"- Output unique mills: {match_audit['output_unique_mills']}",
        f"- Matched source rows: {match_audit['matched_source_rows']}",
        f"- Matched unique mills: {match_audit['matched_unique_mills']}",
        f"- Matched mills found in outputs: {match_audit['matched_mills_found_in_outputs']}",
        f"- Matched mills missing in outputs: {match_audit['matched_mills_missing_in_outputs']}",
        "",
        f"## Mean AGB (Mg/ha): {company_label} vs All Mills ({year_start} & {year_end})",
        "",
        "| Radius (km) | Year | All mills mean | Company mean | Abs diff (company-all) | % diff |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in focus.iterrows():
        company_mean = r[f"mean_{company_group}"]
        lines.append(
            f"| {int(r['radius_km'])} | {int(r['year'])} | {r['mean_ALL_MILLS']:.3f} | {company_mean:.3f} | {r['mean_abs_diff_company_minus_all']:.3f} | {r['mean_pct_diff_company_vs_all']:.2f}% |"
        )

    (out_dir / "analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-company pipeline
# ---------------------------------------------------------------------------

def run_company_analysis(
    all_df: pd.DataFrame,
    change_df: pd.DataFrame,
    spec: CompanySpec,
    out_dir: Path,
    year_start: int,
    year_end: int,
) -> dict[str, object]:
    matched_df, matched_ids = load_company_ids(spec)
    company_group = spec.label.upper().replace(" ", "_")

    grouped = make_grouped_df(all_df, matched_ids, company_group)
    summary = summarize_metrics(grouped, AGB_METRICS)
    comparison = make_comparison_table(summary, company_group, spec.key, spec.label)
    audit = make_match_audit(all_df, matched_df, matched_ids)
    missing_ids = sorted(list(matched_ids - set(all_df["mill_id"].unique())))
    change_summary = summarize_change_by_group(change_df, matched_ids, company_group)

    # Change df with group tag for boxplots
    change_with_group = change_df.copy()
    change_with_group["group"] = np.where(
        change_with_group["mill_id"].isin(matched_ids), company_group, "ALL_MILLS"
    )

    save_company_outputs(out_dir, audit, missing_ids, summary, comparison, change_summary)
    plot_temporal_trends(summary, company_group, spec.label, spec.key, out_dir / "fig_agb_temporal_trends.png")
    plot_change_boxplots(change_with_group, company_group, spec.label, spec.key, out_dir / "fig_agb_change_distributions.png")
    write_company_summary_md(out_dir, spec.label, company_group, audit, comparison, year_start, year_end)

    overview = comparison[comparison["metric"].isin(AGB_METRICS)].copy()
    overview["matched_unique_mills"] = audit["matched_unique_mills"]
    overview["matched_source_rows"] = audit["matched_source_rows"]
    overview["matched_mills_found_in_outputs"] = audit["matched_mills_found_in_outputs"]

    return {
        "overview": overview,
        "change_summary": change_summary,
        "audit": audit,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = (args.out_dir.resolve() if args.out_dir else run_dir / "analysis_companies")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading AGB outputs from: {run_dir}", flush=True)
    all_df = load_agb_outputs(run_dir)

    print("Computing per-mill change metrics...", flush=True)
    change_df = compute_per_mill_change(all_df, args.year_start, args.year_end)

    specs = default_company_specs()
    manifest_rows = []
    overview_frames = []
    change_overview_frames = []

    for spec in specs:
        print(f"Analysing {spec.label}...", flush=True)
        company_out_dir = out_dir / spec.key
        result = run_company_analysis(all_df, change_df, spec, company_out_dir, args.year_start, args.year_end)
        overview_frames.append(result["overview"])
        change_overview_frames.append(result["change_summary"])
        manifest_rows.append({
            "company_key": spec.key,
            "company_label": spec.label,
            "source_csv_count": len(spec.matched_csvs),
            "source_csvs": "; ".join(str(path) for path in spec.matched_csvs),
            **result["audit"],
        })

    # Cross-company outputs
    overview = pd.concat(overview_frames, ignore_index=True)
    overview.to_csv(out_dir / "company_overview_agb_stats.csv", index=False)

    change_overview = pd.concat(change_overview_frames, ignore_index=True)
    # Add company identifiers
    for spec in specs:
        cg = spec.label.upper().replace(" ", "_")
        change_overview.loc[change_overview["group"] == cg, "company_key"] = spec.key
        change_overview.loc[change_overview["group"] == cg, "company_label"] = spec.label
    change_overview.to_csv(out_dir / "company_overview_agb_change.csv", index=False)

    pd.DataFrame(manifest_rows).to_csv(out_dir / "company_manifest.csv", index=False)
    with open(out_dir / "company_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_rows, f, indent=2)

    plot_company_diff_heatmap(overview, out_dir / "fig_company_agb_diff_heatmap.png")
    plot_company_change_summary(change_overview, out_dir / "fig_company_agb_change_summary.png")

    print(f"\nSaved company analyses to: {out_dir}")
    print(pd.DataFrame(manifest_rows)[
        ["company_label", "matched_unique_mills", "matched_mills_found_in_outputs"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
