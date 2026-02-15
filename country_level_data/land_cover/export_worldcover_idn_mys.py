"""
Export ESA WorldCover (2020/2021) for Indonesia + Malaysia as a single GeoTIFF.

Run:
  python3 land_cover/export_worldcover_idn_mys.py --year 2020

Notes:
- Requires Google Earth Engine Python API and authenticated account.
- The export goes to Google Drive by default.
"""

import ee
import argparse


def _init_ee() -> None:
    try:
        ee.Initialize()
    except Exception:
        # First-time auth or expired credentials.
        ee.Authenticate()
        ee.Initialize()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export ESA WorldCover for IDN+MYS.")
    parser.add_argument(
        "--year",
        type=int,
        default=2020,
        choices=[2020, 2021],
        help="WorldCover year to export (2020 or 2021).",
    )
    parser.add_argument(
        "--test-region",
        action="store_true",
        help="Export a small ~3x3 km test region instead of full countries.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _init_ee()

    # ESA WorldCover 10m land cover map by year.
    YEAR = args.year
    dataset_by_year = {
        2020: "ESA/WorldCover/v100",
        2021: "ESA/WorldCover/v200",
    }
    if YEAR not in dataset_by_year:
        raise ValueError(f"Unsupported YEAR {YEAR}. Use 2020 or 2021.")
    worldcover = ee.ImageCollection(dataset_by_year[YEAR]).first().select("Map")

    # Country boundaries (GAUL 2015 level 0) for Indonesia and Malaysia.
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    country_names = ["Indonesia", "Malaysia"]
    regions_fc = countries.filter(ee.Filter.inList("ADM0_NAME", country_names))
    region = regions_fc.geometry()

    # Small test region (~3x3 km) to keep exports lightweight.
    USE_TEST_REGION = args.test_region
    if USE_TEST_REGION:
        import math

        # Pick a fixed point in Malaysia (near Kuala Lumpur).
        test_center_lon = 101.7
        test_center_lat = 3.1
        half_size_km = 1.5  # 3 km / 2

        lat_deg = half_size_km / 111.32
        lon_deg = half_size_km / (111.32 * math.cos(math.radians(test_center_lat)))

        region = ee.Geometry.Rectangle(
            [
                test_center_lon - lon_deg,
                test_center_lat - lat_deg,
                test_center_lon + lon_deg,
                test_center_lat + lat_deg,
            ]
        )

    # Clip to region and export as GeoTIFF(s).
    image = worldcover.clip(region)

    if USE_TEST_REGION:
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=f"esa_worldcover_{YEAR}_test_3km",
            folder=f"gee_worldcover_{YEAR}_test",
            fileNamePrefix=f"esa_worldcover_{YEAR}_test_3km",
            region=region,
            scale=10,
            maxPixels=1e13,
            fileFormat="GeoTIFF",
        )
        task.start()
        print("Test export task started.")
        print(
            f"Check the Earth Engine Tasks tab or Google Drive/gee_worldcover_{YEAR}_test."
        )
        return

    # Real run: single export for both countries.
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=f"esa_worldcover_{YEAR}_idn_mys",
        folder=f"gee_worldcover_{YEAR}_idn_mys",
        fileNamePrefix=f"esa_worldcover_{YEAR}_idn_mys",
        region=region,
        scale=10,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        fileDimensions=[4096, 4096],
        formatOptions={"cloudOptimized": True},
    )
    task.start()
    print("Export task started for Indonesia + Malaysia.")
    print(
        f"Check the Earth Engine Tasks tab or Google Drive/gee_worldcover_{YEAR}_idn_mys."
    )


if __name__ == "__main__":
    main()
