"""
Export ESA CCI Above-Ground Biomass (AGB) + uncertainty for Indonesia + Malaysia.

Run:
  python3 land_cover/export_agb_idn_mys.py --year 2022
  python3 land_cover/export_agb_idn_mys.py --year 2022 --test-region

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
        # First-time auth or expired credentials.
        ee.Authenticate()
        ee.Initialize()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export ESA CCI AGB + uncertainty for IDN+MYS."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2022,
        choices=list(range(2015, 2023)),
        help="AGB year to export (2015-2022).",
    )
    parser.add_argument(
        "--test-region",
        action="store_true",
        help="Export a small ~3x3 km test region instead of full countries.",
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
        default=100.0,
        help="Export pixel size in meters (default: 100).",
    )
    parser.add_argument(
        "--nan-zeros",
        action="store_true",
        help="Treat AGB zeros as missing and export as float with nodata=-9999.",
    )
    return parser.parse_args()


def _get_agb_image(images: ee.ImageCollection, year: int) -> ee.Image:
    """Select the best available image for the requested year."""
    start = ee.Date.fromYMD(year, 1, 1)
    end = start.advance(1, "year")
    by_time = images.filterDate(start, end)
    by_index = images.filter(ee.Filter.stringContains("system:index", str(year)))

    image = ee.Image(
        ee.Algorithms.If(by_time.size().gt(0), by_time.mosaic(), by_index.mosaic())
    )
    # Standardize band names: Band 1 = AGB, Band 2 = uncertainty (SD).
    return image.select([0, 1], ["AGB", "AGB_SD"])


def _get_region(use_test_region: bool, test_size_km: float) -> ee.Geometry:
    # Country boundaries (GAUL 2015 level 0) for Indonesia and Malaysia.
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    country_names = ["Indonesia", "Malaysia"]
    regions_fc = countries.filter(ee.Filter.inList("ADM0_NAME", country_names))
    region = regions_fc.geometry()

    if not use_test_region:
        return region

    # Test region (square) to keep exports lightweight.
    # Pick a fixed point in Malaysia (near Kuala Lumpur).
    test_center_lon = 101.7
    test_center_lat = 3.1
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


def main() -> None:
    args = _parse_args()
    _init_ee()

    year = args.year
    images = ee.ImageCollection("projects/sat-io/open-datasets/ESA/ESA_CCI_AGB")
    image = _get_agb_image(images, year)

    region = _get_region(args.test_region, args.test_size_km)
    image = image.clip(region)

    format_options = {"cloudOptimized": True}
    if args.nan_zeros:
        # Mask out zeros and export as float with explicit nodata value.
        # Note: GEE export does not accept NaN in JSON payloads.
        image = image.updateMask(image.select("AGB").neq(0)).toFloat()
        format_options["noData"] = -9999

    scale = args.scale

    if args.test_region:
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=f"esa_cci_agb_{year}_test_3km",
            folder=f"gee_agb_{year}_test",
            fileNamePrefix=f"esa_cci_agb_{year}_test_3km",
            region=region,
            scale=scale,
            maxPixels=1e13,
            fileFormat="GeoTIFF",
            formatOptions=format_options,
        )
        task.start()
        print("Test export task started.")
        print(f"Check the Earth Engine Tasks tab or Google Drive/gee_agb_{year}_test.")
        return

    # Real run: single export for both countries.
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=f"esa_cci_agb_{year}_idn_mys",
        folder=f"gee_agb_{year}_idn_mys",
        fileNamePrefix=f"esa_cci_agb_{year}_idn_mys",
        region=region,
        scale=scale,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        fileDimensions=[4096, 4096],
        formatOptions=format_options,
    )
    task.start()
    print("Export task started for Indonesia + Malaysia.")
    print(f"Check the Earth Engine Tasks tab or Google Drive/gee_agb_{year}_idn_mys.")


if __name__ == "__main__":
    main()
