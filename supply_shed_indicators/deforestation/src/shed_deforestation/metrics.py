from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import rasterio
from rasterio.coords import BoundingBox
from rasterio.windows import Window, from_bounds


METERS_PER_DEG_LAT = 110_574.0
METERS_PER_DEG_LON_EQUATOR = 111_320.0


@dataclass(frozen=True)
class CircleBounds:
    left: float
    bottom: float
    right: float
    top: float


@dataclass(frozen=True)
class TransitionResult:
    forest_to_nonforest_pixels: int
    forest_to_oilpalm_pixels: int
    forest_to_nonforest_area_ha: float
    forest_to_oilpalm_area_ha: float


def supply_shed_area_ha(radius_km: float) -> float:
    return math.pi * (radius_km ** 2) * 100.0


def circle_bounds_deg(lon: float, lat: float, radius_km: float) -> CircleBounds:
    cos_lat = max(abs(math.cos(math.radians(lat))), 1e-6)
    dlat = radius_km / 110.574
    dlon = radius_km / (111.320 * cos_lat)
    return CircleBounds(
        left=lon - dlon,
        right=lon + dlon,
        bottom=lat - dlat,
        top=lat + dlat,
    )


def classify_coverage(bounds: CircleBounds, raster_bounds: BoundingBox) -> str:
    if (
        bounds.right <= raster_bounds.left
        or bounds.left >= raster_bounds.right
        or bounds.top <= raster_bounds.bottom
        or bounds.bottom >= raster_bounds.top
    ):
        return "NO_COVERAGE"

    if (
        bounds.left >= raster_bounds.left
        and bounds.right <= raster_bounds.right
        and bounds.bottom >= raster_bounds.bottom
        and bounds.top <= raster_bounds.top
    ):
        return "FULL_COVERAGE"

    return "PARTIAL_COVERAGE"


def _integer_window(left: float, bottom: float, right: float, top: float, ds: rasterio.DatasetReader) -> Window:
    win = from_bounds(left, bottom, right, top, transform=ds.transform)
    col_start = int(math.floor(win.col_off))
    row_start = int(math.floor(win.row_off))
    col_stop = int(math.ceil(win.col_off + win.width))
    row_stop = int(math.ceil(win.row_off + win.height))
    width = max(1, col_stop - col_start)
    height = max(1, row_stop - row_start)
    return Window(col_off=col_start, row_off=row_start, width=width, height=height)


def _forest_mask(arr: np.ndarray, forest_classes: Iterable[int]) -> np.ndarray:
    forest_classes = tuple(int(c) for c in forest_classes)
    if len(forest_classes) == 1:
        return arr == forest_classes[0]
    return np.isin(arr, forest_classes)


def _pixel_area_m2(transform: rasterio.Affine, lat: float) -> float:
    cos_lat = max(abs(math.cos(math.radians(lat))), 1e-6)
    pixel_w_m = abs(transform.a) * METERS_PER_DEG_LON_EQUATOR * cos_lat
    pixel_h_m = abs(transform.e) * METERS_PER_DEG_LAT
    return pixel_w_m * pixel_h_m


def count_transitions_in_circle(
    ds20: rasterio.DatasetReader,
    ds21: rasterio.DatasetReader,
    *,
    lon: float,
    lat: float,
    radius_km: float,
    forest_classes: tuple[int, ...],
    oil_palm_class: int,
    nodata_value: int,
    block_rows: int,
) -> TransitionResult:
    radius_m = radius_km * 1000.0
    radius_m2 = radius_m * radius_m

    cb = circle_bounds_deg(lon, lat, radius_km)
    window = _integer_window(cb.left, cb.bottom, cb.right, cb.top, ds20)

    width = int(window.width)
    height = int(window.height)

    col_idx = np.arange(width, dtype=np.float64) + float(window.col_off)
    x_coords = ds20.transform.c + (col_idx + 0.5) * ds20.transform.a

    m_per_deg_lon = METERS_PER_DEG_LON_EQUATOR * max(abs(math.cos(math.radians(lat))), 1e-6)
    dx2 = np.square((x_coords - lon) * m_per_deg_lon)

    count_nonforest = 0
    count_oilpalm = 0

    for row_start_local in range(0, height, block_rows):
        h = min(block_rows, height - row_start_local)
        chunk_win = Window(
            col_off=window.col_off,
            row_off=window.row_off + row_start_local,
            width=window.width,
            height=h,
        )

        arr20 = ds20.read(
            1,
            window=chunk_win,
            boundless=True,
            fill_value=nodata_value,
            out_dtype=np.uint8,
        )
        arr21 = ds21.read(
            1,
            window=chunk_win,
            boundless=True,
            fill_value=nodata_value,
            out_dtype=np.uint8,
        )

        row_idx = np.arange(h, dtype=np.float64) + float(chunk_win.row_off)
        y_coords = ds20.transform.f + (row_idx + 0.5) * ds20.transform.e
        dy2 = np.square((y_coords - lat) * METERS_PER_DEG_LAT)

        inside = (dy2[:, None] + dx2[None, :]) <= radius_m2
        if not inside.any():
            continue

        f20 = _forest_mask(arr20, forest_classes)
        f21 = _forest_mask(arr21, forest_classes)

        forest_to_nonforest = inside & f20 & (~f21)
        forest_to_oilpalm = inside & f20 & (arr21 == oil_palm_class)

        count_nonforest += int(np.count_nonzero(forest_to_nonforest))
        count_oilpalm += int(np.count_nonzero(forest_to_oilpalm))

    pixel_area_m2 = _pixel_area_m2(ds20.transform, lat)
    area_nonforest_ha = count_nonforest * pixel_area_m2 / 10_000.0
    area_oilpalm_ha = count_oilpalm * pixel_area_m2 / 10_000.0

    return TransitionResult(
        forest_to_nonforest_pixels=count_nonforest,
        forest_to_oilpalm_pixels=count_oilpalm,
        forest_to_nonforest_area_ha=area_nonforest_ha,
        forest_to_oilpalm_area_ha=area_oilpalm_ha,
    )
