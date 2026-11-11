import geopandas as gpd, pandas as pd, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
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
gdf=gpd.read_file(f"{OUT}/concessions_labelled.geojson").to_crs(4326)
m=pd.read_csv(f"{OUT}/concession_deforestation_metrics.csv")
gdf=gdf.merge(m[["name","f2nf_ha","f2op_ha","f2nf_rate","f2op_rate"]],on="name",how="left")
rspo=gpd.read_file(RSPO_SHP).to_crs(4326)
minx,miny,maxx,maxy=gdf.total_bounds
rspo_s=rspo.cx[minx-0.1:maxx+0.1,miny-0.1:maxy+0.1]

# Map 1: RSPO label
fig,ax=plt.subplots(figsize=(11,7))
col={"RSPO":"#1a9850","non-RSPO":"#bbbbbb"}
for lab,c in col.items():
    sub=gdf[gdf["rspo_label"]==lab]
    sub.plot(ax=ax,color=c,edgecolor="white",linewidth=0.3,label=f"{lab} (n={len(sub)})")
rspo_s.boundary.plot(ax=ax,color="#d73027",linewidth=0.5,label="RSPO footprint")
ax.set_title("Sarawak oil-palm concessions by RSPO overlap status (T≥50%)",fontsize=13)
ax.legend(loc="lower left",fontsize=9); ax.set_xlabel("lon");ax.set_ylabel("lat")
plt.tight_layout(); plt.savefig(f"{OUT}/map_rspo_label.png",dpi=140); plt.close()

# Map 2: deforestation rate choropleth
fig,ax=plt.subplots(figsize=(11,7))
gdf.plot(ax=ax,column="f2nf_rate",cmap="OrRd",edgecolor="white",linewidth=0.3,
         legend=True,scheme=None,vmin=0,vmax=np.nanpercentile(gdf["f2nf_rate"],95),
         legend_kwds={"label":"Forest→non-forest rate (share of concession area)","shrink":0.6})
ax.set_title("Sarawak concessions: forest→non-forest rate 2020→2021",fontsize=13)
plt.tight_layout(); plt.savefig(f"{OUT}/map_defor_rate.png",dpi=140); plt.close()

# Plot 3: distributions by RSPO label
fig,axes=plt.subplots(1,2,figsize=(11,5))
for ax,col,ti in [(axes[0],"f2nf_rate","Forest→non-forest rate"),(axes[1],"f2op_rate","Forest→oil-palm rate")]:
    data=[gdf.loc[gdf["rspo_label"]==l,col].dropna()*100 for l in ["RSPO","non-RSPO"]]
    bp=ax.boxplot(data,labels=[f"{l}\n(n={int((gdf['rspo_label']==l).sum())})" for l in ["RSPO","non-RSPO"]],showfliers=True,patch_artist=True)
    for patch,c in zip(bp["boxes"],["#1a9850","#bbbbbb"]): patch.set_facecolor(c)
    ax.set_title(ti); ax.set_ylabel("% of concession area")
plt.suptitle("Deforestation rate distribution by RSPO status (2020→2021)",fontsize=13)
plt.tight_layout(); plt.savefig(f"{OUT}/plot_distributions.png",dpi=140); plt.close()
print("saved 3 figures")
