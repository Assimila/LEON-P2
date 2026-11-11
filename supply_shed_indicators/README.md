# Supply-shed indicators (stage 3)

Per-mill statistics inside circular supply sheds (default radii **25 km** and **50 km**)
for every mill in the UML, plus comparisons between all mills and each company's matched
mills.

Inputs (from stages 1–2):

- `company/UML/UML-Dec-2024.csv`
- `country_level_data/land_cover/mosaics/worldcover_{2020,2021}_idn_mys_bias_oilpalm_cog.tif`
- `country_level_data/biomass/mosaics/agb_<year>_idn_mys_cog.tif`
- `country_level_data/fire/mosaics/mcd64a1_burn_any_<year>_idn_mys_cog.tif`
- `company/results/<company>/uml/matched_mills_*.csv`

All paths, radii, years and class codes are set in `<indicator>/configs/default.json`
(relative to the repository root; set `LEON_P2_ROOT` to run from elsewhere).
Each run writes to `<indicator>/outputs/run_<UTC timestamp>/` with a `run_metadata.json`.

## Deforestation (2020 → 2021, bias-corrected WorldCover)

```bash
python3 supply_shed_indicators/deforestation/run_deforestation.py [--limit 50] [--workers 6]
python3 supply_shed_indicators/deforestation/analysis/compare_with_companies.py      # latest run by default
pytest -q supply_shed_indicators/deforestation/tests
```

Per mill × radius: forest→non-forest and forest→oil-palm (class 11) pixel counts, areas (ha)
and shares of the geometric shed area (πr²), plus `coverage_status`
(`FULL_COVERAGE` / `PARTIAL_COVERAGE` / `NO_COVERAGE`). Forest = WorldCover 10 + 95.
Pixel area is approximated from raster resolution and mill latitude.

## Above-ground biomass (2015–2022, ESA CCI)

```bash
python3 supply_shed_indicators/agb/analysis/run_agb_analysis.py [--limit 50]
python3 supply_shed_indicators/agb/analysis/compare_with_companies.py
```

Outputs: `agb_mill_year_stats.csv` (mean / total biomass, valid area per mill × year × radius),
`agb_per_mill_change_2015_2022.csv` (change, % change, CAGR, trend slope) and summaries.

## Fire (2015–2024 by default; data 2001–2024, MODIS MCD64A1)

```bash
python3 supply_shed_indicators/fire/analysis/run_fire_analysis.py [--limit 50]
python3 supply_shed_indicators/fire/analysis/compare_with_companies.py --run-dir supply_shed_indicators/fire/outputs/run_<timestamp>
```

Outputs: `fire_mill_year_stats.csv` (burned pixels, ha, % of shed), `fire_frequency_per_mill.csv`
(years with fire, peak year, trend).

## Interpretation

Sheds overlap in dense mill regions — do not sum per-mill areas into company or national
totals. See `docs/limitations_and_transferability.md`.
