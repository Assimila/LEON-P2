"""
Export GlobalOilPalm YoP (2021) for Indonesia + Malaysia as tiled GeoTIFFs.

Run:
  python3 land_cover/export_oilpalm_yop_idn_mys.py

Notes:
- Requires Google Earth Engine Python API and authenticated account.
- Exports to Google Drive by default (folder name below).
"""

import ee


def _init_ee() -> None:
    try:
        ee.Initialize()
    except Exception:
        ee.Authenticate()
        ee.Initialize()


def main() -> None:
    _init_ee()

    # Countries (GAUL 2015 level 0) for Indonesia and Malaysia.
    countries = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
    region_fc = countries.filter(
        ee.Filter.inList("ADM0_NAME", ["Indonesia", "Malaysia"])
    )
    region = region_fc.geometry()

    # Global Oil Palm YoP 2021 (minNBR_date + lastBareLand_date).
    # Convert date (days since 1970-01-01) to year.
    date_disturbance = (
        ee.ImageCollection("projects/ee-globaloilpalm/assets/shared/GlobalOilPalm_YoP_2021")
        .mosaic()
        .select(["minNBR_date", "lastBareLand_date"])
        .rename(["minNBR", "last"])
    )

    year_disturbance = date_disturbance.divide(365).add(1970)
    mask = year_disturbance.select("minNBR").lt(1990).selfMask()
    yop = year_disturbance.select("minNBR").where(mask, 1989).rename("YoP")

    # Export tiled GeoTIFFs at 30m.
    task = ee.batch.Export.image.toDrive(
        image=yop,
        description="globaloilpalm_yop_2021_idn_mys",
        folder="gee_globaloilpalm_yop_2021_idn_mys",
        fileNamePrefix="globaloilpalm_yop_2021_idn_mys",
        region=region,
        scale=30,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
        fileDimensions=[4096, 4096],
        formatOptions={"cloudOptimized": True},
    )
    task.start()

    print("Export task started for GlobalOilPalm YoP 2021 (IDN+MYS).")
    print("Check the Earth Engine Tasks tab or Google Drive/gee_globaloilpalm_yop_2021_idn_mys.")


if __name__ == "__main__":
    main()
