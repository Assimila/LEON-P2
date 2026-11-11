# Company ↔ Universal Mill List matching (stage 2)

Links companies' public palm-oil supplier disclosures to the **Universal Mill List (UML)**
so that EO indicators computed per mill can be read per company.

## Folder layout (inputs are not versioned)

```
company/
├── UML/UML-Dec-2024.csv          # UML reference table (download separately)
├── report/                        # company disclosure PDFs (download separately)
├── results/<company>/uml/         # outputs (created by the scripts)
└── scripts/
    ├── common/uml_tools.py        # parsing, name normalisation, haversine, UML loader
    ├── danone/   nestle/   ferrero/   pepsico/   wilmar/   unilever/
```

## Scripts

| Company | Command | Matching rule | Default input PDF in `report/` |
|---|---|---|---|
| Danone | `python3 company/scripts/danone/match_danone_reports_to_uml.py` | Mill list (Part A): nearest UML mill to disclosed GPS. Plantation list (Part B): UML ID. Processes every Danone report snapshot found. | `*mill*list*.pdf` (H2-2022, H1-2023, H1-2024, H2-2024) |
| Nestlé | `python3 company/scripts/nestle/match_nestle_mills_to_uml.py` | UML ID; unmatched and missing-ID rows written separately | `responsible-sourcing-disclosure-palm-oil.pdf` |
| Ferrero | `python3 company/scripts/ferrero/match_ferrero_mills_to_uml.py` | UML ID (core + acquired brands) | `palm-oil-mill-list-july-december-2022.pdf` |
| PepsiCo | `python3 company/scripts/pepsico/match_pepsico_mills_to_uml.py` | UML ID | `2024-global-palm-oil-mill-list.pdf` |
| Wilmar | `python3 company/scripts/wilmar/match_wilmar_own_mills_to_uml.py` | UML ID (own mills by country) | `wilmar-own-mill_wilmar-sustainability-241231.pdf` |
| Unilever | `python3 company/scripts/unilever/match_unilever_suppliers_to_uml.py` | Supplier-level list → UML company name (normalised) | `unilever-palm-oil-suppliers-2024.pdf` |

Danone summary figures:

```bash
python3 company/scripts/danone/plot_danone_plantation_distances.py   # plantation→mill distance histograms
python3 company/scripts/danone/plot_danone_rspo_pies.py              # RSPO certification shares
```

Every script accepts `--uml-csv`, `--report`/`--report-dir` and `--output-dir`, so no path
is tied to a particular machine.

## Outputs

`results/<company>/uml/matched_mills_<report>.csv` — UML columns (UML ID, mill, parent
company, country, latitude, longitude, RSPO status, …) for each disclosed mill.
Danone additionally writes `matched_plantations_<report>.csv` with plantation coordinates
and plantation-to-mill distance.

## Caveats

- Disclosures are voluntary, change between releases and can be withdrawn; treat each
  release as a snapshot (e.g. Danone H1-2023 has no plantation coordinates).
- Danone GPS matching uses the nearest UML mill without a distance cap — review rows with
  large distances.
- Mills supplying several companies appear in several company tables.
