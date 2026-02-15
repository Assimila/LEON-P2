#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIGSIZE = (6.5, 6.5)


def classify_rspo(value: str) -> str:
    text = (value or "").strip().lower()
    if "certified" in text and "not" not in text:
        return "RSPO Certified"
    return "Not RSPO Certified"


def count_rspo(csv_path: Path):
    certified = 0
    not_certified = 0
    with csv_path.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = classify_rspo(row.get("RSPO Status", ""))
            if status == "RSPO Certified":
                certified += 1
            else:
                not_certified += 1
    return certified, not_certified


def plot_pie(certified: int, not_certified: int, output_path: Path):
    labels = ["RSPO Certified", "Not RSPO Certified"]
    sizes = [certified, not_certified]
    colors = ["#1f6f78", "#c9cdd3"]
    total = sum(sizes)
    size_iter = iter(sizes)

    def _autopct(_pct):
        count = next(size_iter)
        pct = (count / total * 100.0) if total else 0.0
        return f"{pct:.1f}%"

    plt.style.use("seaborn-v0_8-white")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    wedges, label_texts, pct_texts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        startangle=90,
        counterclock=False,
        autopct=_autopct,
        labeldistance=0.9,
        pctdistance=0.6,
        textprops={"fontsize": 12},
        wedgeprops={"linewidth": 1.2, "edgecolor": "white"},
        normalize=True,
    )
    for t in pct_texts:
        t.set_fontsize(22)
    for t in label_texts:
        t.set_text("")
    ax.axis("equal")
    fig.subplots_adjust(left=0.06, right=0.94, top=0.94, bottom=0.06)
    fig.savefig(output_path, dpi=300)


def main():
    parser = argparse.ArgumentParser(
        description="Plot RSPO certified vs not certified pie charts for matched mills."
    )
    parser.add_argument(
        "--input-dir",
        default="UML",
        help="Directory containing matched_mills_*.csv files",
    )
    parser.add_argument(
        "--output-dir",
        default="UML/rspo_pies",
        help="Directory to save pie charts",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_paths = sorted(input_dir.glob("matched_mills_*.csv"))
    if not csv_paths:
        raise SystemExit(f"No matched_mills CSVs found in {input_dir}")

    for csv_path in csv_paths:
        certified, not_certified = count_rspo(csv_path)
        if certified + not_certified == 0:
            print(f"{csv_path.name}: no rows, skipped")
            continue
        out_path = output_dir / f"{csv_path.stem}_rspo_pie.png"
        plot_pie(certified, not_certified, out_path)
        print(f"{csv_path.name}: certified={certified}, not_certified={not_certified}")
        print(f"Pie saved: {out_path}")


if __name__ == "__main__":
    main()
