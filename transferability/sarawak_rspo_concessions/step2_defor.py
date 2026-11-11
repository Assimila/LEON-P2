import geopandas as gpd, pandas as pd, numpy as np, math
import rasterio
from rasterio.mask import raster_geometry_mask
from rasterio.windows import from_bounds
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path

# Paths are configurable through environment variables:
#   LEON_P2_ROOT        repository root (default: two levels above this folder)
#   CONCESSION_DATA_DIR folder holding Sarawak_oil_palm_concessions/ and RSPO/ shapefiles
#   CONCESSION_OUT_DIR  output folder (default: ./outputs next to this script)
_HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(os.environ.get("LEON_P2_ROOT", _HERE.parents[1]))
BASE = os.environ.get("CONCESSION_DATA_DIR", str(_HERE / "data"))
OUT = os.environ.get("CONCESSION_OUT_DIR", str(_HERE / "outputs"))
LC = str(REPO_ROOT / "country_level_data" / "land_cover" / "mosaics")
RSPO_SHP = os.path.join(BASE, "RSPO", "RSPO Concessions Versions 14 – April 2026.shp")
os.makedirs(OUT, exist_ok=True)

R20=f"{LC}/worldcover_2020_idn_mys_bias_oilpalm_cog.tif"
R21=f"{LC}/worldcover_2021_idn_mys_bias_oilpalm_cog.tif"
FOREST={10,95}; OILPALM=11
MPD_LAT=110574.0; MPD_LON=111320.0

gdf=gpd.read_file(f"{OUT}/concessions_labelled.geojson").to_crs(4326)

ds20=rasterio.open(R20); ds21=rasterio.open(R21)
rb=ds20.bounds

def coverage(geom):
    l,b,r,t=geom.bounds
    if r<=rb.left or l>=rb.right or t<=rb.bottom or b>=rb.top: return "NO_COVERAGE"
    if l>=rb.left and r<=rb.right and b>=rb.bottom and t<=rb.top: return "FULL_COVERAGE"
    return "PARTIAL_COVERAGE"

rows=[]
for idx,row in gdf.iterrows():
    geom=row.geometry
    cov=coverage(geom)
    if cov=="NO_COVERAGE":
        rows.append(dict(idx=idx, coverage=cov, f2nf_px=np.nan,f2op_px=np.nan,
                         f2nf_ha=np.nan,f2op_ha=np.nan, valid_px=np.nan)); continue
    # window from geom bounds
    l,b,r,t=geom.bounds
    win=from_bounds(max(l,rb.left),max(b,rb.bottom),min(r,rb.right),min(t,rb.top),ds20.transform)
    # rasterize mask of polygon over this window
    mask,_,mwin = raster_geometry_mask(ds20,[geom.__geo_interface__],crop=True,all_touched=False)
    inside=~mask  # True inside polygon
    a20=ds20.read(1,window=mwin,boundless=True,fill_value=0).astype(np.uint8)
    a21=ds21.read(1,window=mwin,boundless=True,fill_value=0).astype(np.uint8)
    # align shapes
    h=min(inside.shape[0],a20.shape[0],a21.shape[0]); w=min(inside.shape[1],a20.shape[1],a21.shape[1])
    inside=inside[:h,:w]; a20=a20[:h,:w]; a21=a21[:h,:w]
    f20=np.isin(a20,list(FOREST)); f21=np.isin(a21,list(FOREST))
    valid=inside & (a20!=0)
    f2nf=inside & f20 & (~f21)
    f2op=inside & f20 & (a21==OILPALM)
    # pixel area at centroid latitude
    lat=geom.centroid.y
    cos_lat=max(abs(math.cos(math.radians(lat))),1e-6)
    px_w=abs(ds20.transform.a)*MPD_LON*cos_lat; px_h=abs(ds20.transform.e)*MPD_LAT
    px_ha=px_w*px_h/1e4
    rows.append(dict(idx=idx, coverage=cov,
        f2nf_px=int(f2nf.sum()), f2op_px=int(f2op.sum()),
        f2nf_ha=float(f2nf.sum())*px_ha, f2op_ha=float(f2op.sum())*px_ha,
        valid_px=int(valid.sum()), valid_ha=float(valid.sum())*px_ha))

m=pd.DataFrame(rows).set_index("idx")
out=gdf.drop(columns="geometry").join(m)
out["f2nf_rate"]=out["f2nf_ha"]/out["conc_area_ha"]
out["f2op_rate"]=out["f2op_ha"]/out["conc_area_ha"]
out.to_csv(f"{OUT}/concession_deforestation_metrics.csv",index=False)
print("coverage:", out["coverage"].value_counts().to_dict())
print("total forest->non-forest ha:", round(out["f2nf_ha"].sum(),1))
print("total forest->oil palm ha:", round(out["f2op_ha"].sum(),1))
print("median f2nf_rate:", round(out["f2nf_rate"].median(),5))
print("saved concession_deforestation_metrics.csv, n=",len(out))
