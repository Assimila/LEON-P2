import pandas as pd, numpy as np
from scipy.stats import mannwhitneyu
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
df=pd.read_csv(f"{OUT}/concession_deforestation_metrics.csv")

def summ(g):
    return pd.Series(dict(
        n=len(g),
        total_area_ha=g["conc_area_ha"].sum(),
        # area-weighted rates
        f2nf_ha=g["f2nf_ha"].sum(), f2op_ha=g["f2op_ha"].sum(),
        aw_f2nf_rate=g["f2nf_ha"].sum()/g["conc_area_ha"].sum(),
        aw_f2op_rate=g["f2op_ha"].sum()/g["conc_area_ha"].sum(),
        # per-concession means/medians
        mean_f2nf_rate=g["f2nf_rate"].mean(), median_f2nf_rate=g["f2nf_rate"].median(),
        mean_f2op_rate=g["f2op_rate"].mean(), median_f2op_rate=g["f2op_rate"].median(),
    ))

rows=[]
for T in ["rspo_label","rspo_T10","rspo_T25","rspo_T75","rspo_any"]:
    s=df.groupby(T).apply(summ)
    s["threshold"]=T
    rows.append(s.reset_index().rename(columns={T:"group"}))
allS=pd.concat(rows)
allS.to_csv(f"{OUT}/rspo_vs_nonrspo_summary.csv",index=False)

# default T50 detailed
print("=== DEFAULT T=50% stratified summary ===")
d=df.groupby("rspo_label").apply(summ)
print(d[["n","total_area_ha","f2nf_ha","aw_f2nf_rate","mean_f2nf_rate","median_f2nf_rate","aw_f2op_rate","median_f2op_rate"]].round(5).to_string())

# Mann-Whitney on per-concession f2nf rate
a=df.loc[df["rspo_label"]=="RSPO","f2nf_rate"].dropna()
b=df.loc[df["rspo_label"]=="non-RSPO","f2nf_rate"].dropna()
u,p=mannwhitneyu(a,b,alternative="two-sided")
print(f"\nMann-Whitney f2nf_rate RSPO(n={len(a)}) vs non-RSPO(n={len(b)}): U={u:.0f} p={p:.4f}")
a2=df.loc[df["rspo_label"]=="RSPO","f2op_rate"].dropna()
b2=df.loc[df["rspo_label"]=="non-RSPO","f2op_rate"].dropna()
u2,p2=mannwhitneyu(a2,b2,alternative="two-sided")
print(f"Mann-Whitney f2op_rate: U={u2:.0f} p={p2:.4f}")

# label sensitivity table
sens=[]
for c,name in [("rspo_any","any>0"),("rspo_T10","T>=10%"),("rspo_T25","T>=25%"),("rspo_label","T>=50%"),("rspo_T75","T>=75%")]:
    n=(df[c]=="RSPO").sum(); sens.append(dict(rule=name,RSPO=n,nonRSPO=len(df)-n))
pd.DataFrame(sens).to_csv(f"{OUT}/label_sensitivity.csv",index=False)

# owner-group breakdown (top groups)
grp=df.groupby("name_of_gr").agg(n=("name","count"),area_ha=("conc_area_ha","sum"),
     f2nf_ha=("f2nf_ha","sum"),f2op_ha=("f2op_ha","sum")).sort_values("area_ha",ascending=False)
grp["f2nf_rate"]=grp["f2nf_ha"]/grp["area_ha"]
grp.head(15).to_csv(f"{OUT}/owner_group_breakdown.csv")
print("\n=== Top owner groups by area ===")
print(grp.head(10)[["n","area_ha","f2nf_ha","f2nf_rate"]].round(4).to_string())
print("\nsaved summary CSVs")
