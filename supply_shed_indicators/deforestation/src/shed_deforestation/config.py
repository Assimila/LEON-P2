from __future__ import annotations
import os

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = PACKAGE_ROOT.parent.parent
PROJECT_ROOT = Path(os.environ.get("LEON_P2_ROOT", EXPERIMENT_ROOT.parent.parent))
DEFAULT_CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "default.json"


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    mills_csv: Path
    worldcover_2020_tif: Path
    worldcover_2021_tif: Path
    radii_km: tuple[float, ...]
    forest_classes: tuple[int, ...]
    oil_palm_class: int
    nodata_value: int
    block_rows: int
    default_workers: int
    output_root: Path


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _to_tuple_int(values: list[Any]) -> tuple[int, ...]:
    return tuple(int(v) for v in values)


def _to_tuple_float(values: list[Any]) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def load_config(config_path: Path | None = None) -> ExperimentConfig:
    cfg_path = config_path or DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return ExperimentConfig(
        experiment_name=str(raw["experiment_name"]),
        mills_csv=_resolve_path(raw["mills_csv"]),
        worldcover_2020_tif=_resolve_path(raw["worldcover_2020_tif"]),
        worldcover_2021_tif=_resolve_path(raw["worldcover_2021_tif"]),
        radii_km=_to_tuple_float(raw["radii_km"]),
        forest_classes=_to_tuple_int(raw["forest_classes"]),
        oil_palm_class=int(raw["oil_palm_class"]),
        nodata_value=int(raw["nodata_value"]),
        block_rows=int(raw.get("block_rows", 1024)),
        default_workers=int(raw.get("default_workers", 1)),
        output_root=_resolve_path(raw["output_root"]),
    )
