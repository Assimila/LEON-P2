"""
Export MODIS BurnDate (MCD64A1 v6.1) for Indonesia + Malaysia as a single-band
annual burn mask (1 if any month burned in the year, else 0).

Run:
  python3 fire/export_modis_burn_any_idn_mys.py --year 2024
  python3 fire/export_modis_burn_any_idn_mys.py --year 2024 --test-region

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
        description="Export MODIS BurnDate annual burn mask for IDN+MYS."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Year to export (e.g., 2024).",
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
        default=500.0,
        help="Export pixel size in meters (default: 500).",
    )
    return parser.parse_args()


def _get_region(use_test_region: bool, test_size_km: float) -> ee.Geometry:
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    country_names = ["Indonesia", "Malaysia"]
    regions_fc = countries.filter(ee.Filter.inList("ADM0_NAME", country_names))
    region = regions_fc.geometry()

    if not use_test_region:
        return region

    # Test region (square) centered near Kuala Lumpur.
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


def _annual_burn_mask(year: int) -> ee.Image:
    start_date = ee.Date.fromYMD(year, 1, 1)
    end_date = start_date.advance(1, "year")

    collection = (
        ee.ImageCollection("MODIS/061/MCD64A1")
        .filterDate(start_date, end_date)
        .select("BurnDate")
    )

    # BurnDate > 0 indicates a burn detected in that month.
    burn_any = collection.map(lambda img: img.gt(0)).max()
    return burn_any.rename("burned_any").toByte()


def main() -> None:
    args = _parse_args()
    _init_ee()

    image = _annual_burn_mask(args.year)
    region = _get_region(args.test_region, args.test_size_km)
    image = image.clip(region)

    description_suffix = "test_3km" if args.test_region else f"idn_mys_{args.year}"
    folder_suffix = "test" if args.test_region else f"idn_mys_{args.year}"

    export_kwargs = dict(
        image=image,
        description=f"modis_mcd64a1_burn_any_{description_suffix}",
        folder=f"gee_mcd64a1_burn_any_{folder_suffix}",
        fileNamePrefix=f"modis_mcd64a1_burn_any_{description_suffix}",
        region=region,
        scale=args.scale,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )

    if not args.test_region:
        export_kwargs["fileDimensions"] = [4096, 4096]

    task = ee.batch.Export.image.toDrive(**export_kwargs)
    task.start()

    print("Export task started.")
    print(
        f"Check the Earth Engine Tasks tab or Google Drive/gee_mcd64a1_burn_any_{folder_suffix}."
    )


if __name__ == "__main__":
    main()
