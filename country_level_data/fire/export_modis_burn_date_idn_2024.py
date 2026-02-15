"""
Export MODIS BurnDate (MCD64A1 v6.1) for Indonesia for 2024 as a multi-band GeoTIFF.

Run:
  python3 fire/export_modis_burn_date_idn_2024.py
  python3 fire/export_modis_burn_date_idn_2024.py --test-region

Notes:
- Requires Google Earth Engine Python API and authenticated account.
- The export goes to Google Drive by default.
"""

import argparse
import math

import ee


def _init_ee() -> None:
    try:
        ee.Initialize()
    except Exception:
        ee.Authenticate()
        ee.Initialize()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export MODIS BurnDate for Indonesia (2024)."
    )
    parser.add_argument(
        "--start-date",
        default="2024-01-01",
        help="Start date (inclusive). Default: 2024-01-01.",
    )
    parser.add_argument(
        "--end-date",
        default="2025-01-01",
        help="End date (exclusive). Default: 2025-01-01.",
    )
    parser.add_argument(
        "--test-region",
        action="store_true",
        help="Export a small ~3x3 km test region instead of full Indonesia.",
    )
    parser.add_argument(
        "--test-size-km",
        type=float,
        default=3.0,
        help="Test region size in km (square). Default: 3.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=500.0,
        help="Export pixel size in meters (default: 500).",
    )
    return parser.parse_args()


def _get_region(use_test_region: bool, test_size_km: float) -> ee.Geometry:
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    region = countries.filter(ee.Filter.eq("ADM0_NAME", "Indonesia")).geometry()

    if not use_test_region:
        return region

    # Test region (square) centered near Jakarta.
    test_center_lon = 106.8456
    test_center_lat = -6.2088
    half_size_km = test_size_km / 2.0

    lat_deg = half_size_km / 111.32
    lon_deg = half_size_km / (111.32 * math.cos(math.radians(test_center_lat)))

    return ee.Geometry.Rectangle(
        [
            test_center_lon - lon_deg,
            test_center_lat - lat_deg,
            test_center_lon + lon_deg,
            test_center_lat + lat_deg,
        ]
    )


def _monthly_burn_date_stack(
    start_date: str, end_date: str
) -> tuple[ee.Image, ee.List]:
    collection = (
        ee.ImageCollection("MODIS/061/MCD64A1")
        .filterDate(start_date, end_date)
        .select("BurnDate")
        .map(
            lambda img: img.set(
                "band_name",
                ee.Date(img.get("system:time_start")).format("YYYY_MM"),
            )
        )
    )
    bands = collection.toBands()
    band_names = ee.List(collection.aggregate_array("band_name"))
    bands = bands.rename(band_names)
    return bands, band_names


def main() -> None:
    args = _parse_args()
    _init_ee()

    image, band_names = _monthly_burn_date_stack(args.start_date, args.end_date)
    region = _get_region(args.test_region, args.test_size_km)
    image = image.clip(region)

    description_suffix = "test_3km" if args.test_region else "idn_2024"
    folder_suffix = "test" if args.test_region else "idn_2024"

    task = ee.batch.Export.image.toDrive(
        image=image,
        description=f"modis_mcd64a1_burn_date_{description_suffix}",
        folder=f"gee_mcd64a1_burn_date_{folder_suffix}",
        fileNamePrefix=f"modis_mcd64a1_burn_date_{description_suffix}",
        region=region,
        scale=args.scale,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    task.start()

    print("Export task started.")
    print("Bands:", band_names.getInfo())
    print(f"Check the Earth Engine Tasks tab or Google Drive/gee_mcd64a1_burn_date_{folder_suffix}.")


if __name__ == "__main__":
    main()
