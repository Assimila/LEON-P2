# Transfer case: Sarawak oil-palm concessions × RSPO

Applies the Pilot 2 deforestation logic (bias-corrected WorldCover 2020 → 2021) to
**concession polygons** instead of mill supply sheds, and compares RSPO-linked with
non-RSPO concessions. Used in the LEON Impact Assessment (D3.1, §4.2.3.1.2).

| Step | Script | Output (in `outputs/`) |
|---|---|---|
| 1 | `step1_label.py` — overlap of each of the 248 concessions with the RSPO concessions footprint (v14, April 2026), computed in equal-area EPSG:6933; labels at 10/25/50/75 % thresholds (default 50 %). | `concessions_labelled.{csv,geojson}` |
| 2 | `step2_defor.py` — forest (10, 95) → non-forest and forest → oil palm (11) area inside each polygon. | `concession_deforestation_metrics.csv` |
| 3 | `step3_analysis.py` — area-weighted and per-concession rates, Mann–Whitney tests, threshold sensitivity, owner-group breakdown. | `rspo_vs_nonrspo_summary.csv`, `label_sensitivity.csv`, `owner_group_breakdown.csv` |
| 4 | `step4_maps.py` — maps and distributions. | `map_rspo_label.png`, `map_defor_rate.png`, `plot_distributions.png` |

## Inputs

```
transferability/sarawak_rspo_concessions/data/
├── Sarawak_oil_palm_concessions/Sarawak_oil_palm_concessions.shp   # Global Forest Watch
└── RSPO/RSPO Concessions Versions 14 – April 2026.shp              # GeoRSPO
```

plus the stage-1 rasters in `country_level_data/land_cover/mosaics/`.
Override locations with `CONCESSION_DATA_DIR`, `CONCESSION_OUT_DIR` and `LEON_P2_ROOT`.

```bash
cd transferability/sarawak_rspo_concessions
for s in step1_label step2_defor step3_analysis step4_maps; do python3 $s.py; done
```

## Interpretation

"RSPO" here means overlap with a mapped RSPO member estate — the layer has no certification
status or dates, so it is a membership footprint, not a certification-quality flag. Higher
forest → oil-palm conversion in RSPO-linked concessions most likely reflects active
planting sites submitting maps to RSPO, not an effect of membership.
