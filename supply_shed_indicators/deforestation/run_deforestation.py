#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shed_deforestation.runner import run_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run per-mill 2020-2021 deforestation metrics using WorldCover 2020/2021 local COG rasters."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=THIS_DIR / "configs" / "default.json",
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output run directory override",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for debugging",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default from config)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_experiment(
        config_path=args.config,
        output_dir=args.output_dir,
        limit=args.limit,
        workers=args.workers,
    )
    print(f"Run directory: {outputs['run_dir']}")


if __name__ == "__main__":
    main()
