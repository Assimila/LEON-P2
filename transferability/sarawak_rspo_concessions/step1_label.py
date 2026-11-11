import geopandas as gpd, pandas as pd, numpy as np
from shapely.ops import unary_union
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

EA="EPSG:3395"  # not equal-area; use a proper equal-area for Borneo instead:
# Use World Cylindrical Equal Area (EPSG:6933) for area math over this small region -> fine.
EA="EPSG:6933"

sar = gpd.read_file(f"{BASE}/Sarawak_oil_palm_concessions/Sarawak_oil_palm_concessions.shp")
rspo = gpd.read_file(RSPO_SHP)
print("Sarawak CRS", sar.crs, "n", len(sar))
print("RSPO CRS", rspo.crs, "n", len(rspo))

# force 2D
sar["geometry"] = sar.geometry.force_2d()
sar = sar.to_crs(4326)
rspo = rspo.to_crs(4326)

# fix invalid geoms
sar["geometry"] = sar.geometry.buffer(0)
# Spatially filter RSPO to Sarawak bbox (+ small pad) BEFORE dissolve for speed
minx,miny,maxx,maxy = sar.total_bounds
pad=0.2
rspo_sar = rspo.cx[minx-pad:maxx+pad, miny-pad:maxy+pad].copy()
print("RSPO polys in Sarawak bbox:", len(rspo_sar), "| by State field:",
      (rspo['State'].astype(str).str.strip().str.lower()=='sarawak').sum())
rspo_sar["geometry"]=rspo_sar.geometry.buffer(0)

# equal-area for area math
sar_ea = sar.to_crs(EA)
sar_ea["conc_area_ha"] = sar_ea.geometry.area/1e4

# QA: compare computed area vs shape_Area(m2 in web mercator) and area_offic
sar_ea["shp_area_ha_field"] = sar["shape_Area"].astype(float)/1e4  # web-merc m2 -> ha (distorted)
print("\n=== AREA QA (equal-area computed) ===")
print(sar_ea["conc_area_ha"].describe()[["min","50%","max","mean"]])
print("total concession area (ha):", round(sar_ea["conc_area_ha"].sum(),1))

# Dissolve RSPO footprint (union) in equal-area
rspo_ea = rspo_sar.to_crs(EA)
foot = unary_union(rspo_ea.geometry.values)
print("RSPO footprint area (ha):", round(foot.area/1e4,1))

# per-concession overlap
recs=[]
rspo_ea_sindex = rspo_ea.sindex
for idx,row in sar_ea.iterrows():
    g=row.geometry
    inter = g.intersection(foot)
    ov = inter.area/1e4 if not inter.is_empty else 0.0
    pct = ov/row["conc_area_ha"] if row["conc_area_ha"]>0 else 0.0
    # matched RSPO member by largest overlap
    matched_parent=""; matched_cat=""; matched_ov=0.0
    for j in rspo_ea_sindex.query(g, predicate="intersects"):
        rg=rspo_ea.iloc[j]
        a=g.intersection(rg.geometry).area
        if a>matched_ov:
            matched_ov=a; matched_parent=str(rg.get("Parent","")); matched_cat=str(rg.get("MemberCat",""))
    recs.append(dict(idx=idx, name=row.get("name",""), group=row.get("name_of_gr",""),
                     conc_area_ha=row["conc_area_ha"], rspo_overlap_ha=ov, overlap_pct=pct,
                     matched_parent=matched_parent, matched_membercat=matched_cat))
lab=pd.DataFrame(recs)

# name agreement (cheap token check)
def name_agree(g,p):
    g=str(g).lower(); p=str(p).lower()
    if not g.strip() or not p.strip(): return False
    toks=[t for t in g.replace("(","").replace(")","").split() if len(t)>3]
    return any(t in p for t in toks)
lab["name_agreement"]=[name_agree(g,p) for g,p in zip(lab["group"],lab["matched_parent"])]

for T in [0.10,0.25,0.50,0.75]:
    lab[f"rspo_T{int(T*100)}"]=np.where(lab["overlap_pct"]>=T,"RSPO","non-RSPO")
lab["rspo_any"]=np.where(lab["overlap_pct"]>0,"RSPO","non-RSPO")
lab["rspo_label"]=lab["rspo_T50"]  # default

print("\n=== LABEL SENSITIVITY (n concessions = %d) ==="%len(lab))
for c,name in [("rspo_any","any>0"),("rspo_T10","T>=10%"),("rspo_T25","T>=25%"),("rspo_T50","T>=50% (default)"),("rspo_T75","T>=75%")]:
    n=(lab[c]=="RSPO").sum(); print(f"  {name:20s} RSPO={n:3d}  non-RSPO={len(lab)-n:3d}")
print("\nConcessions with any overlap:", (lab['overlap_pct']>0).sum())
print("Name-agreement among any-overlap:", lab.loc[lab['overlap_pct']>0,'name_agreement'].sum())

lab.to_csv(f"{OUT}/concessions_labelled.csv", index=False)
# also save geo with labels for defor step (in 4326)
sar_out = sar.copy()
sar_out["conc_area_ha"]=sar_ea["conc_area_ha"].values
for c in ["overlap_pct","rspo_label","rspo_T10","rspo_T25","rspo_T75","rspo_any","matched_parent","name_agreement"]:
    sar_out[c]=lab.set_index("idx").loc[sar_out.index, c].values
sar_keep = sar_out[["name","name_of_gr","conc_area_ha","overlap_pct","rspo_label","rspo_T10","rspo_T25","rspo_T75","rspo_any","matched_parent","name_agreement","geometry"]].copy()
sar_keep.to_file(f"{OUT}/concessions_labelled.geojson", driver="GeoJSON")
print("\nsaved concessions_labelled.csv / .geojson")
