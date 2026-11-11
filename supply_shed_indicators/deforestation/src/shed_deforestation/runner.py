from __future__ import annotations

import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import rasterio

from .config import ExperimentConfig, load_config
from .metrics import (
    CircleBounds,
    circle_bounds_deg,
    classify_coverage,
    count_transitions_in_circle,
    supply_shed_area_ha,
)
from .mills import load_mills


@dataclass(frozen=True)
class WorkerConfig:
    tif_2020: str
    tif_2021: str
    forest_classes: tuple[int, ...]
    oil_palm_class: int
    nodata_value: int
    block_rows: int


_WORKER_DS20: rasterio.DatasetReader | None = None
_WORKER_DS21: rasterio.DatasetReader | None = None
_WORKER_CFG: WorkerConfig | None = None


def _init_worker(cfg: WorkerConfig) -> None:
    global _WORKER_DS20, _WORKER_DS21, _WORKER_CFG
    _WORKER_CFG = cfg
    _WORKER_DS20 = rasterio.open(cfg.tif_2020)
    _WORKER_DS21 = rasterio.open(cfg.tif_2021)


def _row_payload(row: dict[str, Any], radius_km: float) -> dict[str, Any]:
    return {
        "mill_id": str(row["mill_id"]),
        "mill_name": str(row["mill_name"]),
        "iso": str(row["iso"]),
        "country": str(row["country"]),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "radius_km": float(radius_km),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "forest_to_nonforest_pixels": np.nan,
        "forest_to_oilpalm_pixels": np.nan,
        "forest_to_nonforest_area_ha": np.nan,
        "forest_to_oilpalm_area_ha": np.nan,
        "forest_to_nonforest_ratio": np.nan,
        "forest_to_oilpalm_ratio": np.nan,
        "forest_to_nonforest_pct_of_supply_shed": np.nan,
        "forest_to_oilpalm_pct_of_supply_shed": np.nan,
    }


def _process_one(task: dict[str, Any]) -> dict[str, Any]:
    assert _WORKER_DS20 is not None
    assert _WORKER_DS21 is not None
    assert _WORKER_CFG is not None

    lon = task["longitude"]
    lat = task["latitude"]
    radius_km = task["radius_km"]

    bounds: CircleBounds = circle_bounds_deg(lon, lat, radius_km)
    coverage_status = classify_coverage(bounds, _WORKER_DS20.bounds)
    denom_ha = supply_shed_area_ha(radius_km)

    record = {
        "mill_id": task["mill_id"],
        "mill_name": task["mill_name"],
        "iso": task["iso"],
        "country": task["country"],
        "latitude": lat,
        "longitude": lon,
        "radius_km": radius_km,
        "supply_shed_area_ha": denom_ha,
        "coverage_status": coverage_status,
    }

    if coverage_status == "NO_COVERAGE":
        record.update(_empty_metrics())
        return record

    result = count_transitions_in_circle(
        _WORKER_DS20,
        _WORKER_DS21,
        lon=lon,
        lat=lat,
        radius_km=radius_km,
        forest_classes=_WORKER_CFG.forest_classes,
        oil_palm_class=_WORKER_CFG.oil_palm_class,
        nodata_value=_WORKER_CFG.nodata_value,
        block_rows=_WORKER_CFG.block_rows,
    )

    ratio_nonforest = result.forest_to_nonforest_area_ha / denom_ha if denom_ha > 0 else np.nan
    ratio_oilpalm = result.forest_to_oilpalm_area_ha / denom_ha if denom_ha > 0 else np.nan

    record.update({
        "forest_to_nonforest_pixels": result.forest_to_nonforest_pixels,
        "forest_to_oilpalm_pixels": result.forest_to_oilpalm_pixels,
        "forest_to_nonforest_area_ha": result.forest_to_nonforest_area_ha,
        "forest_to_oilpalm_area_ha": result.forest_to_oilpalm_area_ha,
        "forest_to_nonforest_ratio": ratio_nonforest,
        "forest_to_oilpalm_ratio": ratio_oilpalm,
        "forest_to_nonforest_pct_of_supply_shed": ratio_nonforest * 100.0,
        "forest_to_oilpalm_pct_of_supply_shed": ratio_oilpalm * 100.0,
    })
    return record


def _validate_rasters(cfg: ExperimentConfig) -> None:
    with rasterio.open(cfg.worldcover_2020_tif) as ds20, rasterio.open(cfg.worldcover_2021_tif) as ds21:
        if ds20.crs != ds21.crs:
            raise ValueError(f"CRS mismatch: {ds20.crs} vs {ds21.crs}")
        if ds20.transform != ds21.transform:
            raise ValueError("Transform mismatch between 2020 and 2021 rasters")
        if ds20.width != ds21.width or ds20.height != ds21.height:
            raise ValueError("Raster dimensions mismatch between 2020 and 2021 rasters")
        if ds20.count != 1 or ds21.count != 1:
            raise ValueError("Expected single-band rasters")
        if not math.isclose(ds20.transform.b, 0.0, abs_tol=1e-12) or not math.isclose(ds20.transform.d, 0.0, abs_tol=1e-12):
            raise ValueError("Only north-up rasters (no rotation/shear) are supported")


def _run_radius(
    tasks: list[dict[str, Any]],
    worker_cfg: WorkerConfig,
    workers: int,
    *,
    progress_prefix: str,
) -> pd.DataFrame:
    total = len(tasks)
    results: list[dict[str, Any]] = []

    if workers <= 1:
        _init_worker(worker_cfg)
        for idx, task in enumerate(tasks, start=1):
            results.append(_process_one(task))
            if idx % 25 == 0 or idx == total:
                print(f"[{progress_prefix}] {idx}/{total} mills processed", flush=True)
    else:
        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_worker,
                initargs=(worker_cfg,),
            ) as pool:
                for idx, rec in enumerate(pool.map(_process_one, tasks, chunksize=4), start=1):
                    results.append(rec)
                    if idx % 25 == 0 or idx == total:
                        print(f"[{progress_prefix}] {idx}/{total} mills processed", flush=True)
        except PermissionError as exc:
            print(
                f"[{progress_prefix}] Parallel processing unavailable ({exc}); "
                "falling back to single-process mode.",
                flush=True,
            )
            _init_worker(worker_cfg)
            for idx, task in enumerate(tasks, start=1):
                results.append(_process_one(task))
                if idx % 25 == 0 or idx == total:
                    print(f"[{progress_prefix}] {idx}/{total} mills processed", flush=True)

    df = pd.DataFrame(results)
    return df.sort_values(["mill_id", "radius_km"]).reset_index(drop=True)


def run_experiment(
    *,
    config_path: Path | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    workers: int | None = None,
) -> dict[str, Path]:
    cfg = load_config(config_path)
    _validate_rasters(cfg)

    mills = load_mills(cfg.mills_csv, limit=limit)
    worker_count = int(workers if workers is not None else cfg.default_workers)
    worker_count = max(worker_count, 1)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (output_dir or cfg.output_root / f"run_{timestamp}").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(mills)} mills", flush=True)
    print(f"Using {worker_count} worker(s)", flush=True)

    worker_cfg = WorkerConfig(
        tif_2020=str(cfg.worldcover_2020_tif),
        tif_2021=str(cfg.worldcover_2021_tif),
        forest_classes=cfg.forest_classes,
        oil_palm_class=cfg.oil_palm_class,
        nodata_value=cfg.nodata_value,
        block_rows=cfg.block_rows,
    )

    started = time.time()
    radius_outputs: list[Path] = []
    frames: list[pd.DataFrame] = []

    mills_records = mills.to_dict(orient="records")

    for radius in cfg.radii_km:
        tasks = [_row_payload(row, radius) for row in mills_records]
        df_radius = _run_radius(tasks, worker_cfg, worker_count, progress_prefix=f"{int(radius)}km")
        out_csv = run_dir / f"mill_deforestation_metrics_{int(radius)}km.csv"
        df_radius.to_csv(out_csv, index=False)
        radius_outputs.append(out_csv)
        frames.append(df_radius)
        print(f"Wrote {out_csv}", flush=True)

    combined = pd.concat(frames, ignore_index=True)
    combined_csv = run_dir / "mill_deforestation_metrics_all_radii.csv"
    combined.to_csv(combined_csv, index=False)

    runtime_sec = time.time() - started
    metadata = {
        "run_timestamp_utc": timestamp,
        "runtime_seconds": round(runtime_sec, 3),
        "mills_total": int(len(mills)),
        "radii_km": list(cfg.radii_km),
        "forest_classes": list(cfg.forest_classes),
        "oil_palm_class": cfg.oil_palm_class,
        "ratio_denominator": "full_geometric_circle_area",
        "no_coverage_policy": "NA_with_coverage_status",
        "workers": worker_count,
        "config": {
            "mills_csv": str(cfg.mills_csv),
            "worldcover_2020_tif": str(cfg.worldcover_2020_tif),
            "worldcover_2021_tif": str(cfg.worldcover_2021_tif),
            "nodata_value": cfg.nodata_value,
            "block_rows": cfg.block_rows,
        },
        "outputs": {
            "per_radius": [str(p) for p in radius_outputs],
            "combined": str(combined_csv),
        },
    }
    metadata_path = run_dir / "run_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Wrote {combined_csv}", flush=True)
    print(f"Wrote {metadata_path}", flush=True)

    return {
        "run_dir": run_dir,
        "combined_csv": combined_csv,
        "metadata_json": metadata_path,
    }
