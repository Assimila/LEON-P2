from __future__ import annotations

import math

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from shed_deforestation.metrics import (
    CircleBounds,
    classify_coverage,
    count_transitions_in_circle,
    supply_shed_area_ha,
)


def _make_mem_raster(arr: np.ndarray):
    transform = from_origin(0.0, 3.0, 0.01, 0.01)
    mem = MemoryFile()
    ds = mem.open(
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        transform=transform,
        nodata=0,
    )
    ds.write(arr, 1)
    return mem, ds


def test_supply_shed_area_ha_formula():
    area = supply_shed_area_ha(25)
    expected = math.pi * 25 * 25 * 100
    assert math.isclose(area, expected, rel_tol=0, abs_tol=1e-9)


def test_classify_coverage():
    raster_bounds = rasterio.coords.BoundingBox(left=0, bottom=0, right=10, top=10)
    assert classify_coverage(CircleBounds(2, 2, 8, 8), raster_bounds) == "FULL_COVERAGE"
    assert classify_coverage(CircleBounds(-2, 2, 3, 8), raster_bounds) == "PARTIAL_COVERAGE"
    assert classify_coverage(CircleBounds(-5, -5, -1, -1), raster_bounds) == "NO_COVERAGE"


def test_count_transitions_in_circle_small_raster():
    arr20 = np.array(
        [
            [10, 10, 50],
            [95, 10, 11],
            [50, 95, 10],
        ],
        dtype=np.uint8,
    )
    arr21 = np.array(
        [
            [50, 11, 50],
            [95, 80, 11],
            [50, 95, 10],
        ],
        dtype=np.uint8,
    )

    mem20, ds20 = _make_mem_raster(arr20)
    mem21, ds21 = _make_mem_raster(arr21)

    try:
        result = count_transitions_in_circle(
            ds20,
            ds21,
            lon=0.015,
            lat=2.985,
            radius_km=500,
            forest_classes=(10, 95),
            oil_palm_class=11,
            nodata_value=0,
            block_rows=16,
        )
    finally:
        ds20.close()
        ds21.close()
        mem20.close()
        mem21.close()

    assert result.forest_to_nonforest_pixels == 3
    assert result.forest_to_oilpalm_pixels == 1
    assert result.forest_to_oilpalm_area_ha <= result.forest_to_nonforest_area_ha
