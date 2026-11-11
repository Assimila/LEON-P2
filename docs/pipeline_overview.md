# Pipeline overview

The Pilot 2 workflow follows the eight processing stages described in the ATBD (D2.2).
This table maps each stage to the code in this repository.

| # | ATBD stage | What happens | Code | Main outputs |
|---|---|---|---|---|
| 1 | Mill geolocation | Company disclosures (PDF) parsed and matched to the Universal Mill List: by disclosed UML ID where available (Nestlé, Ferrero, PepsiCo, Wilmar, Danone plantation lists), by nearest UML mill to disclosed GPS coordinates for Danone mill lists, and by normalised company name for supplier-level lists (Unilever). Danone H2-2024: 197 matched mills. | `company/scripts/<company>/match_*.py`, shared helpers in `company/scripts/common/uml_tools.py` | `company/results/<company>/uml/matched_mills_*.csv`, `matched_plantations_*.csv` |
| 2 | Supply-shed generation | Circular 25 km and 50 km buffers around each mill (geometric circle; area = πr²). Plantation-to-mill distance distributions justify the 25 km choice. | buffers built inside each stage-3 runner; distance analysis in `company/scripts/danone/plot_danone_plantation_distances.py` | — |
| 3 | Deforestation detection | WorldCover 2020/2021 exported from GEE, mosaicked to COG; pixels with oil-palm year-of-planting ≤ target year recoded to class 11 (bias correction); forest = classes 10 + 95; per-pixel forest→non-forest and forest→oil-palm transitions counted inside each shed. | `country_level_data/land_cover/` (RUNBOOK) → `supply_shed_indicators/deforestation/` | `worldcover_<yr>_idn_mys_bias_oilpalm_cog.tif`; `mill_deforestation_metrics_{25,50}km.csv` |
| 4 | AGB zonal statistics | ESA CCI AGB (100 m, with SD band) per year 2015–2022, mosaicked; mean/min/max and change/trend per shed. | `country_level_data/biomass/` (RUNBOOK) → `supply_shed_indicators/agb/` | `agb_<yr>_idn_mys_cog.tif`; `agb_mill_year_stats.csv`, `agb_per_mill_change_2015_2022.csv` |
| 5 | Fire incidence | MCD64A1 monthly BurnDate reduced to annual burned/not-burned masks; per shed burned area, % of shed, fire frequency and trend. | `country_level_data/fire/` (RUNBOOK) → `supply_shed_indicators/fire/` | `mcd64a1_burn_any_<yr>_idn_mys_cog.tif`; `fire_mill_year_stats.csv`, `fire_frequency_per_mill.csv` |
| 6 | BII estimation | PREDICTS (Indonesia + Malaysia) mixed-effects models for total abundance and Bray–Curtis similarity, projected onto the bias-corrected land cover (+ Forest Landscape Integrity) inside 25 km sheds; median and sum BII per mill. | `Indonesia_Malaysia_Biodiversity_Inctactness_Index/` (R / Quarto, A. Etard) | `5_companies_BII.csv`; per-mill BII GeoTIFFs |
| 7 | RSPO metadata merge | RSPO status carried from UML into matched-mill tables; RSPO pie charts. | `company/scripts/danone/plot_danone_rspo_pies.py` | `rspo_pies/*.png` |
| 8 | Export / comparison | All-mills vs company-mills comparisons, per-company tables and figures; CSV + COG feed the dashboard. | `supply_shed_indicators/*/analysis/compare_with_companies.py` | `analysis_companies/…` |

## Automation and manual hand-offs

| Hand-off | Status in this release |
|---|---|
| GEE task monitoring | Scripted: `tools/monitor_gee_tasks.py --filter <name> --wait` |
| rclone configuration | One-off; documented in `docs/gee_and_rclone_setup.md`. All download scripts take `--remote`. |
| Company matching paths | No hard-coded paths. Defaults resolve relative to `company/`; every input/output overridable by CLI flag. |
| Stage-3 paths | Resolved from JSON configs relative to the repo root (`LEON_P2_ROOT` override). |
| Python ↔ R hand-off (BII) | BII reads the stage-1 bias-corrected land cover and the stage-2 matched-mill CSVs; inputs and folder layout are described in `Indonesia_Malaysia_Biodiversity_Inctactness_Index/Quarto_Indonesia_Malaysia.qmd`. |

## Reproducing the Danone demonstration case end-to-end

```bash
# Stage 1 (see each RUNBOOK for the export/download steps)
python3 country_level_data/land_cover/export_worldcover_idn_mys.py         # 2020 & 2021
python3 country_level_data/land_cover/export_oilpalm_yop_idn_mys.py
python3 tools/monitor_gee_tasks.py --wait
# ... rclone download + mosaic + bias correction (land_cover/RUNBOOK.md)

# Stage 2
python3 company/scripts/danone/match_danone_reports_to_uml.py

# Stage 3
python3 supply_shed_indicators/deforestation/run_deforestation.py
python3 supply_shed_indicators/agb/analysis/run_agb_analysis.py
python3 supply_shed_indicators/fire/analysis/run_fire_analysis.py

# Stage 4 (R)
cd Indonesia_Malaysia_Biodiversity_Inctactness_Index && quarto render Quarto_Indonesia_Malaysia.qmd
```
