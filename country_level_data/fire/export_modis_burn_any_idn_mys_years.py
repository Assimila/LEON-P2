"""
Batch export MODIS BurnDate (MCD64A1 v6.1) annual burn-any masks for IDN+MYS.

Run:
  python3 fire/export_modis_burn_any_idn_mys_years.py --start-year 2001 --end-year 2023

Notes:
- Requires Google Earth Engine Python API and authenticated account.
- Exports go to Google Drive by default.
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
        description="Batch export MODIS BurnDate annual burn masks for IDN+MYS."
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2001,
        help="First year to export (inclusive). Default: 2001.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2023,
        help="Last year to export (inclusive). Default: 2023.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=500.0,
        help="Export pixel size in meters (default: 500).",
    )
    return parser.parse_args()


def _get_region() -> ee.Geometry:
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    country_names = ["Indonesia", "Malaysia"]
    regions_fc = countries.filter(ee.Filter.inList("ADM0_NAME", country_names))
    return regions_fc.geometry()


def _annual_burn_mask(year: int) -> ee.Image:
    start_date = ee.Date.fromYMD(year, 1, 1)
    end_date = start_date.advance(1, "year")

    collection = (
        ee.ImageCollection("MODIS/061/MCD64A1")
        .filterDate(start_date, end_date)
        .select("BurnDate")
    )

    burn_any = collection.map(lambda img: img.gt(0)).max()
    return burn_any.rename("burned_any").toByte()


def main() -> None:
    args = _parse_args()
    _init_ee()

    start_year = args.start_year
    end_year = args.end_year
    if end_year < start_year:
        raise ValueError("--end-year must be >= --start-year.")

    region = _get_region()

    for year in range(start_year, end_year + 1):
        image = _annual_burn_mask(year).clip(region)
        description_suffix = f"idn_mys_{year}"
        folder_suffix = f"idn_mys_{year}"

        task = ee.batch.Export.image.toDrive(
            image=image,
            description=f"modis_mcd64a1_burn_any_{description_suffix}",
            folder=f"gee_mcd64a1_burn_any_{folder_suffix}",
            fileNamePrefix=f"modis_mcd64a1_burn_any_{description_suffix}",
            region=region,
            scale=args.scale,
            maxPixels=1e13,
            fileFormat="GeoTIFF",
            fileDimensions=[4096, 4096],
            formatOptions={"cloudOptimized": True},
        )
        task.start()
        print(f"Started export for {year}.")

    print("All export tasks submitted.")


if __name__ == "__main__":
    main()
