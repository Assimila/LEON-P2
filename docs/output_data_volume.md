# Output Experimental Dataset — data volume (Pilot 2)

Measured from the production run (file sizes of the delivered formats: Cloud-Optimised
GeoTIFF for rasters, CSV for tables). Coverage: Indonesia + Malaysia.

| Dataset family | Files | Format | Period | Volume |
|---|---|---|---|---|
| WorldCover land cover (original, IDN+MYS mosaics) | 2 | COG, 10 m, Byte | 2020, 2021 | 2.07 GB |
| Bias-corrected land cover (oil palm = class 11) | 2 | COG, 10 m, Byte | 2020, 2021 | 3.59 GB |
| Oil-palm year-of-planting context layer | 1 | COG, 10 m | 2021 | 0.35 GB |
| Above-ground biomass + uncertainty band | 8 | COG, 100 m, Float32 ×2 bands | 2015–2022 | 5.77 GB (≈0.72 GB / year) |
| Fire occurrence (annual burned/not burned) | 24 | COG, ~500 m, Byte | 2001–2024 | 2.7 MB |
| Company ↔ UML mill/plantation matching (6 companies + UML reference) | 35 | CSV | H2-2022 – 2024 | 4.8 MB |
| Supply-shed indicator tables (deforestation, AGB, fire; 25 & 50 km; all UML mills) | 17 | CSV | as above | 19.6 MB |
| BII summary per mill (5 companies) | 1 | CSV | 2020, 2021 | 0.6 MB |
| BII gridded rasters per mill area (1,858 unique mills × 2 years ≈ 3,700 files) | ~3,700 | GeoTIFF, ~100 m | 2020, 2021 | **≈1–4 GB (estimate)** |
| **Total** | | | | **≈ 11.8 GB measured + ≈1–4 GB BII rasters → ≈ 13–16 GB** |

Notes

- The BII raster volume is estimated from the per-mill grid size implied by the BII tables
  (~1.6 × 10⁵ cells per 25 km supply shed at ~100 m; 0.3–1 MB per compressed GeoTIFF).
- Rasters dominate (>99 % of volume). Tables are small enough for direct download.
- Growth if extended: each extra year of 10 m land cover adds ≈1.0 GB (raw) + ≈1.8 GB
  (bias-corrected); each extra AGB year ≈0.72 GB; each extra fire year ≈0.1 MB. Extending
  stage 3 to new companies only adds tables (MB scale).
