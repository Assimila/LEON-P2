# LEON Pilot 2 — Agrifood Supply Chains (Land Conversion)

Open-source workflow of the ESA-funded **LEON** project (*Leveraging Earth Observation for
Nature finance*), Pilot 2. It turns openly available Earth Observation (EO) products into
**asset-level (per-mill supply-shed) environmental indicators** for oil palm supply chains in
Indonesia and Malaysia, linked to companies' public supplier disclosures.

| Indicator | Source product | Resolution | Period |
|---|---|---|---|
| Deforestation (forest → non-forest; forest → oil palm), bias-corrected | ESA WorldCover v100 (2020) / v200 (2021) + Global Oil Palm year-of-planting 2021 (Descals et al. 2024) | 10 m | 2020 → 2021 |
| Above-ground biomass (mean / min / max, uncertainty) | ESA CCI Biomass v6.0 | 100 m | 2015–2022 |
| Fire incidence (annual burned / not burned) | MODIS MCD64A1 v6.1 | ~500 m | 2001–2024 |
| Biodiversity Intactness Index (BII) | PREDICTS mixed-effects models applied to bias-corrected land cover | ~100 m | 2020, 2021 |
| Company ↔ mill ↔ plantation links, RSPO status | Universal Mill List (UML, Dec 2024) + company disclosures | point | H2-2022 – 2024 |

Supply sheds are circular buffers of **25 km** (primary; captures 73.3 % of Danone's disclosed
plantation-to-mill links) and **50 km** (sensitivity; 88.0 %) around each UML mill.

Method details: *D2.2 Algorithm Theoretical Basis Document (ATBD), Pilot 2*; validation:
*D2.3 Product Validation Report*; outputs: *D2.5 Output Experimental Dataset*.

---

## Repository layout

```
LEON-P2/
├── country_level_data/          # Stage 1 – national-scale EO rasters (GEE export → rclone → GDAL COG)
│   ├── land_cover/              #   WorldCover 2020/2021, oil-palm YoP, bias correction   (RUNBOOK.md)
│   ├── biomass/                 #   ESA CCI AGB 2015–2022                                 (RUNBOOK.md)
│   └── fire/                    #   MODIS MCD64A1 annual burn masks 2001–2024             (RUNBOOK.md)
├── company/                     # Stage 2 – match company disclosures to the Universal Mill List
│   └── scripts/{common,danone,nestle,ferrero,pepsico,wilmar,unilever}/
├── supply_shed_indicators/      # Stage 3 – per-mill 25/50 km statistics + company comparisons
│   ├── deforestation/           #   (package, config, unit tests)
│   ├── agb/
│   └── fire/
├── Indonesia_Malaysia_Biodiversity_Inctactness_Index/  # Stage 4 – BII for mill areas (R / Quarto; A. Etard, IIASA)
├── transferability/             # Transfer case: Sarawak oil-palm concessions × RSPO
├── tools/monitor_gee_tasks.py   # Poll / wait on GEE export tasks from the command line
├── docs/                        # Pipeline, limitations, data volumes, GEE/rclone setup
├── requirements.txt             # Pinned Python dependencies
├── environment.yml              # Conda env incl. pinned GDAL + rclone
├── CITATION.cff
└── LICENSE                      # CC BY-NC 4.0
```

See **[docs/pipeline_overview.md](docs/pipeline_overview.md)** for the stage-by-stage
description that maps each script to the ATBD processing steps.

## Quick start

```bash
git clone https://github.com/Assimila/LEON-P2.git && cd LEON-P2

# Option A – conda (recommended: also provides GDAL CLI + rclone)
conda env create -f environment.yml && conda activate leon-p2

# Option B – pip only (Python stages; GDAL CLI must be installed separately for *.sh scripts)
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Earth Engine (stage 1 only)
earthengine authenticate
```

Then follow, in order:

1. `country_level_data/land_cover/RUNBOOK.md`, `biomass/RUNBOOK.md`, `fire/RUNBOOK.md`
2. `company/README.md`
3. `supply_shed_indicators/README.md`
4. `Indonesia_Malaysia_Biodiversity_Inctactness_Index/Quarto_Indonesia_Malaysia.qmd` (rendered: `Quarto_Indonesia_Malaysia.html`)

Every script accepts `--help`. All default paths are resolved relative to the repository
root (override with `LEON_P2_ROOT=/path/to/LEON-P2`), so nothing depends on a particular machine.

Run the unit tests:

```bash
pytest -q supply_shed_indicators/deforestation/tests
```

## Inputs you must obtain

Large inputs and outputs are **not** stored in Git (see `.gitignore`).

| Input | Where to get it | Expected location |
|---|---|---|
| ESA WorldCover, ESA CCI Biomass, MODIS MCD64A1, Global Oil Palm YoP | Exported from Google Earth Engine by the stage 1 scripts | `country_level_data/*/mosaics/` |
| Universal Mill List (Dec 2024) | https://www.globalforestwatch.org/ (UML, WRI consortium) | `company/UML/UML-Dec-2024.csv` |
| Company supplier disclosures (PDF) | Public company websites (see `company/README.md`) | `company/report/` |
| PREDICTS database | https://data.nhm.ac.uk/dataset/?tags=predicts | see `Indonesia_Malaysia_Biodiversity_Inctactness_Index/Quarto_Indonesia_Malaysia.qmd` |
| Sarawak concessions, RSPO concessions v14 | Global Forest Watch / RSPO GeoRSPO | `transferability/sarawak_rspo_concessions/data/` |

## Computing requirements

- Google Earth Engine account and Cloud project. GEE is free for non-commercial / research
  use; **commercial users need a paid Earth Engine licence**. All GEE steps only export
  public catalogue data, so equivalent rasters can be produced on other platforms
  (e.g. Copernicus Data Space Ecosystem, Microsoft Planetary Computer) and dropped into the
  `mosaics/` folders; stages 2–4 do not use GEE.
- ~20 GB free disk for national mosaics (see [docs/output_data_volume.md](docs/output_data_volume.md)).
- Stage 3 runs on a laptop (multiprocessing; ~1,800 mills × 2 radii in minutes to tens of minutes).
- Stage 4 requires R and Quarto with the packages listed at the top of `Indonesia_Malaysia_Biodiversity_Inctactness_Index/Quarto_Indonesia_Malaysia.qmd`.

## Limitations (read before use)

The outputs are **screening indicators**, not compliance determinations. Key caveats —
including the 2020–2021 limit of WorldCover change detection, deferred quantitative
deforestation accuracy metrics, probabilistic (not causal) mill attribution, overlapping
supply sheds, AGB saturation and MODIS small-fire omission — are documented in
**[docs/limitations_and_transferability.md](docs/limitations_and_transferability.md)**.

## Licence

Code and documentation: **CC BY-NC 4.0** (Attribution-NonCommercial 4.0 International) —
see [LICENSE](LICENSE). All LEON Output Experimental Datasets are released under the same
licence. Third-party datasets keep their own terms (e.g. PREDICTS recent releases are
non-commercial; the UML and company disclosures are subject to their publishers' terms).

## Citation and contact

Please cite using [CITATION.cff](CITATION.cff). Contributors: Rui Song (Global Canopy),
Adrienne Etard (IIASA), Claudia Gray, Fiona Pedeboy, Nicola Wilson (Global Canopy),
Gerardo López-Saldaña (Assimila). LEON is funded by the European Space Agency.
Project website: https://www.leon-naturefinance.org/
