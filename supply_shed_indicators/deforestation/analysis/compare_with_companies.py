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


KEY_METRICS = [
    "forest_to_nonforest_area_ha",
    "forest_to_oilpalm_area_ha",
    "forest_to_nonforest_pct_of_supply_shed",
    "forest_to_oilpalm_pct_of_supply_shed",
]

ALL_METRICS = [
    "forest_to_nonforest_pixels",
    "forest_to_oilpalm_pixels",
    "forest_to_nonforest_area_ha",
    "forest_to_oilpalm_area_ha",
    "forest_to_nonforest_pct_of_supply_shed",
    "forest_to_oilpalm_pct_of_supply_shed",
    "oilpalm_share_of_nonforest_area_pct",
]

METRIC_LABELS = {
    "forest_to_nonforest_pixels": "Forest to Non-Forest (pixels)",
    "forest_to_oilpalm_pixels": "Forest to Oil Palm (pixels)",
    "forest_to_nonforest_area_ha": "Forest to Non-Forest (ha)",
    "forest_to_oilpalm_area_ha": "Forest to Oil Palm (ha)",
    "forest_to_nonforest_pct_of_supply_shed": "Forest to Non-Forest (% of supply shed)",
    "forest_to_oilpalm_pct_of_supply_shed": "Forest to Oil Palm (% of supply shed)",
    "oilpalm_share_of_nonforest_area_pct": "Oil Palm Share of Forest Loss (%)",
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

DEFAULT_RUN_DIR = _latest_run(PROJECT_ROOT / "supply_shed_indicators" / "deforestation" / "outputs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare deforestation metrics for all mills vs matched company mill sets."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        required=DEFAULT_RUN_DIR is None,
        help="Run directory containing 25km/50km outputs",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: <run-dir>/analysis_companies)",
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


def load_all_mill_outputs(run_dir: Path) -> pd.DataFrame:
    df25 = pd.read_csv(run_dir / "mill_deforestation_metrics_25km.csv")
    df50 = pd.read_csv(run_dir / "mill_deforestation_metrics_50km.csv")
    all_df = pd.concat([df25, df50], ignore_index=True)
    all_df = _standardize_cols(all_df)
    all_df["mill_id"] = all_df["mill_id"].astype(str).str.strip()
    return all_df


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


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    denom = out["forest_to_nonforest_area_ha"]
    numer = out["forest_to_oilpalm_area_ha"]
    out["oilpalm_share_of_nonforest_area_pct"] = np.where(
        (denom.notna()) & (denom > 0),
        numer / denom * 100.0,
        np.nan,
    )
    return out


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

    for (radius, group), sub in grouped.groupby(["radius_km", "group"], sort=True):
        for metric in metrics:
            s = pd.to_numeric(sub[metric], errors="coerce")
            non_na = s.dropna()
            n = int(non_na.shape[0])
            std = float(non_na.std(ddof=1)) if n > 1 else np.nan
            se = std / np.sqrt(n) if n > 1 else np.nan
            ci95 = 1.96 * se if n > 1 else np.nan
            rows.append(
                {
                    "radius_km": float(radius),
                    "group": group,
                    "metric": metric,
                    "metric_label": METRIC_LABELS.get(metric, metric),
                    "n_total_rows": int(sub.shape[0]),
                    "n_non_null": n,
                    "coverage_full": int((sub["coverage_status"] == "FULL_COVERAGE").sum()),
                    "coverage_partial": int((sub["coverage_status"] == "PARTIAL_COVERAGE").sum()),
                    "coverage_none": int((sub["coverage_status"] == "NO_COVERAGE").sum()),
                    "mean": float(non_na.mean()) if n else np.nan,
                    "median": float(non_na.median()) if n else np.nan,
                    "std": std,
                    "min": float(non_na.min()) if n else np.nan,
                    "p25": float(non_na.quantile(0.25)) if n else np.nan,
                    "p75": float(non_na.quantile(0.75)) if n else np.nan,
                    "max": float(non_na.max()) if n else np.nan,
                    "ci95": ci95,
                }
            )

    return pd.DataFrame(rows)


def make_comparison_table(summary: pd.DataFrame, company_group: str, company_key: str, company_label: str) -> pd.DataFrame:
    piv = summary.pivot_table(
        index=["radius_km", "metric", "metric_label"],
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
    out["median_abs_diff_company_minus_all"] = out[f"median_{company_group}"] - out["median_ALL_MILLS"]
    out["median_pct_diff_company_vs_all"] = np.where(
        out["median_ALL_MILLS"].abs() > 0,
        (out[f"median_{company_group}"] - out["median_ALL_MILLS"]) / out["median_ALL_MILLS"] * 100.0,
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


def set_plot_style() -> None:
    plt.rcParams.update(
        {
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
        }
    )


def _style_axis(ax: plt.Axes) -> None:
    ax.set_axisbelow(True)
    ax.grid(False)
    ax.spines["left"].set_color("#4a4a4a")
    ax.spines["bottom"].set_color("#4a4a4a")


def plot_key_metrics_bar(summary: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_path: Path) -> None:
    set_plot_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    axes = axes.flatten()
    company_color = COMPANY_COLORS[company_key]

    for ax, metric in zip(axes, KEY_METRICS):
        sub = summary[summary["metric"] == metric].copy()
        radii = sorted(sub["radius_km"].unique())
        x = np.arange(len(radii), dtype=float)
        w = 0.24

        for i, (group, color, label) in enumerate(
            [
                ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
                (company_group, company_color, company_label),
            ]
        ):
            g = sub[sub["group"] == group].set_index("radius_km").reindex(radii)
            means = g["mean"].to_numpy(dtype=float)
            errs = g["ci95"].to_numpy(dtype=float)
            errs = np.where(np.isfinite(errs), errs, 0.0)

            ax.bar(
                x + (-w / 2 if i == 0 else w / 2),
                means,
                width=w,
                color=color,
                label=label,
                yerr=errs,
                capsize=2.2,
                error_kw={"elinewidth": 0.9, "capthick": 0.9, "ecolor": "#333333"},
                edgecolor="#ffffff",
                linewidth=0.7,
            )

        ax.set_xticks(x)
        ax.set_xticklabels([f"{int(r)} km" for r in radii])
        ax.set_title(METRIC_LABELS.get(metric, metric))
        ax.set_ylabel("Value")
        _style_axis(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(f"All Mills vs {company_label}: Mean Comparison with 95% CI", fontsize=14, y=1.05)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_distribution_box(grouped: pd.DataFrame, company_group: str, company_label: str, company_key: str, out_path: Path) -> None:
    set_plot_style()
    metrics = ["forest_to_nonforest_area_ha", "forest_to_oilpalm_pct_of_supply_shed"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), constrained_layout=True)

    for ax, metric in zip(axes, metrics):
        labels = []
        data = []
        colors = []
        for radius in [25.0, 50.0]:
            for group, color, label in [
                ("ALL_MILLS", ALL_MILLS_COLOR, "All Mills"),
                (company_group, COMPANY_COLORS[company_key], company_label),
            ]:
                sub = grouped[(grouped["radius_km"] == radius) & (grouped["group"] == group)][metric].dropna()
                labels.append(f"{int(radius)}km\n{label}")
                data.append(sub.to_numpy())
                colors.append(color)

        bp = ax.boxplot(
            data,
            patch_artist=True,
            tick_labels=labels,
            showfliers=False,
            widths=0.58,
            whiskerprops={"color": "#4a4a4a", "linewidth": 0.9},
            capprops={"color": "#4a4a4a", "linewidth": 0.9},
            boxprops={"edgecolor": "#4a4a4a", "linewidth": 0.9},
            medianprops={"color": "#1a1a1a", "linewidth": 1.2},
        )
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)

        ax.set_title(METRIC_LABELS[metric])
        ax.set_ylabel("Value")
        _style_axis(ax)

    fig.suptitle(f"Distribution Comparison: All Mills vs {company_label}", fontsize=14)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_coverage_stacked(coverage: pd.DataFrame, company_group: str, company_label: str, out_path: Path) -> None:
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

        ax.bar(
            x,
            vals,
            bottom=bottoms,
            width=0.56,
            color=status_colors[status],
            label=status.replace("_", " "),
            edgecolor="white",
            linewidth=0.7,
        )
        bottoms += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Share of Mills (%)")
    ax.set_title(f"Coverage Status Composition: All Mills vs {company_label}")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right")
    _style_axis(ax)

    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_company_diff_heatmap(overview: pd.DataFrame, out_path: Path) -> None:
    set_plot_style()
    metrics = [
        "forest_to_nonforest_pct_of_supply_shed",
        "forest_to_oilpalm_pct_of_supply_shed",
        "oilpalm_share_of_nonforest_area_pct",
    ]
    columns = [(25.0, metric) for metric in metrics] + [(50.0, metric) for metric in metrics]
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
    ax.set_xticklabels(
        [
            f"{int(radius)}km\n{METRIC_LABELS[metric].replace(' (% of supply shed)', '').replace(' (%)', '')}"
            for radius, metric in columns
        ]
    )
    ax.set_yticks(np.arange(len(companies)))
    ax.set_yticklabels(companies)
    ax.set_title("Company vs All Mills: Mean % Difference")

    for i in range(len(companies)):
        for j in range(len(columns)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center", fontsize=8, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cbar.set_label("% difference vs all mills")
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def save_company_outputs(
    out_dir: Path,
    match_audit: dict,
    missing_ids: list[str],
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "match_audit.json", "w", encoding="utf-8") as f:
        json.dump(match_audit, f, indent=2)

    pd.DataFrame({"missing_mill_id": missing_ids}).to_csv(
        out_dir / "matched_mills_missing_in_outputs.csv", index=False
    )

    summary.to_csv(out_dir / "summary_stats_long.csv", index=False)
    comparison.to_csv(out_dir / "comparison_key_stats.csv", index=False)
    coverage.to_csv(out_dir / "coverage_status_summary.csv", index=False)


def write_company_summary_md(
    out_dir: Path,
    company_label: str,
    company_group: str,
    match_audit: dict,
    comparison: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    focus = comparison[comparison["metric"].isin(KEY_METRICS)].copy()
    focus = focus.sort_values(["radius_km", "metric"])

    coverage_piv = coverage.pivot_table(
        index=["radius_km", "group"],
        columns="coverage_status",
        values="share_pct",
        aggfunc="first",
    ).reset_index().fillna(0.0)

    lines = [
        f"# All Mills vs {company_label}",
        "",
        "## Match Audit",
        f"- Output unique mills: {match_audit['output_unique_mills']}",
        f"- Matched source rows: {match_audit['matched_source_rows']}",
        f"- Matched unique mills: {match_audit['matched_unique_mills']}",
        f"- Matched mills found in outputs: {match_audit['matched_mills_found_in_outputs']}",
        f"- Matched mills missing in outputs: {match_audit['matched_mills_missing_in_outputs']}",
        "",
        "## Key Mean Comparison",
        "",
        "| Radius (km) | Metric | All mills mean | Company mean | Abs diff (company-all) | % diff |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for _, row in focus.iterrows():
        company_mean = row[f"mean_{company_group}"]
        lines.append(
            f"| {int(row['radius_km'])} | {row['metric']} | {row['mean_ALL_MILLS']:.4f} | {company_mean:.4f} | {row['mean_abs_diff_company_minus_all']:.4f} | {row['mean_pct_diff_company_vs_all']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Coverage Summary (%)",
            "",
            "| Radius (km) | Group | FULL | PARTIAL | NONE |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for _, row in coverage_piv.sort_values(["radius_km", "group"]).iterrows():
        lines.append(
            f"| {int(row['radius_km'])} | {row['group']} | {row.get('FULL_COVERAGE', 0.0):.2f}% | {row.get('PARTIAL_COVERAGE', 0.0):.2f}% | {row.get('NO_COVERAGE', 0.0):.2f}% |"
        )

    (out_dir / "analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_company_analysis(all_df: pd.DataFrame, spec: CompanySpec, out_dir: Path) -> dict[str, object]:
    matched_df, matched_ids = load_company_ids(spec)
    company_group = spec.label.upper().replace(" ", "_")

    grouped = make_grouped_df(all_df, matched_ids, company_group)
    summary = summarize_metrics(grouped, ALL_METRICS)
    comparison = make_comparison_table(summary, company_group, spec.key, spec.label)
    coverage = summarize_coverage(grouped)
    audit = make_match_audit(all_df, matched_df, matched_ids)
    missing_ids = sorted(list(matched_ids - set(all_df["mill_id"].unique())))

    save_company_outputs(out_dir, audit, missing_ids, summary, comparison, coverage)
    plot_key_metrics_bar(summary, company_group, spec.label, spec.key, out_dir / "fig_key_metric_means_ci.png")
    plot_key_metrics_bar(summary, company_group, spec.label, spec.key, out_dir / "fig_key_metric_means_ci.pdf")
    plot_distribution_box(grouped, company_group, spec.label, spec.key, out_dir / "fig_distributions_boxplot.png")
    plot_distribution_box(grouped, company_group, spec.label, spec.key, out_dir / "fig_distributions_boxplot.pdf")
    plot_coverage_stacked(coverage, company_group, spec.label, out_dir / "fig_coverage_composition.png")
    plot_coverage_stacked(coverage, company_group, spec.label, out_dir / "fig_coverage_composition.pdf")
    write_company_summary_md(out_dir, spec.label, company_group, audit, comparison, coverage)

    overview = comparison[comparison["metric"].isin(ALL_METRICS)].copy()
    overview["matched_unique_mills"] = audit["matched_unique_mills"]
    overview["matched_source_rows"] = audit["matched_source_rows"]
    overview["matched_mills_found_in_outputs"] = audit["matched_mills_found_in_outputs"]
    return {
        "overview": overview,
        "audit": audit,
    }


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = (args.out_dir.resolve() if args.out_dir else run_dir / "analysis_companies")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_df = add_derived_metrics(load_all_mill_outputs(run_dir))

    specs = default_company_specs()
    manifest_rows = []
    overview_frames = []
    for spec in specs:
        company_out_dir = out_dir / spec.key
        result = run_company_analysis(all_df, spec, company_out_dir)
        overview_frames.append(result["overview"])
        manifest_rows.append(
            {
                "company_key": spec.key,
                "company_label": spec.label,
                "source_csv_count": len(spec.matched_csvs),
                "source_csvs": "; ".join(str(path) for path in spec.matched_csvs),
                **result["audit"],
            }
        )

    overview = pd.concat(overview_frames, ignore_index=True)
    overview.to_csv(out_dir / "company_overview_key_stats.csv", index=False)
    pd.DataFrame(manifest_rows).to_csv(out_dir / "company_manifest.csv", index=False)
    with open(out_dir / "company_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_rows, f, indent=2)

    plot_company_diff_heatmap(overview, out_dir / "fig_company_diff_heatmap.png")
    plot_company_diff_heatmap(overview, out_dir / "fig_company_diff_heatmap.pdf")

    print(f"Saved company analyses to: {out_dir}")
    print(pd.DataFrame(manifest_rows)[["company_label", "matched_unique_mills", "matched_mills_found_in_outputs"]].to_string(index=False))


if __name__ == "__main__":
    main()
