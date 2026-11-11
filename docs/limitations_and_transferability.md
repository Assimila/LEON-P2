# Limitations and transferability

These notes summarise what users should know before relying on Pilot 2 outputs, drawing on
the ATBD, the PVR and the LEON Impact Assessment (D3.1). Outputs are **screening
indicators** that flag supply sheds for further investigation; they are not definitive
judgements on a company's performance or on regulatory compliance.

## Indicator-level limitations

| Topic | Limitation | Practical guidance |
|---|---|---|
| Deforestation period | ESA WorldCover exists only for 2020 and 2021, so change detection covers **2020 → 2021 only**. | For post-2021 conversion (e.g. EUDR due diligence after the 31-12-2020 cut-off) the land-cover step must be fed with another annual product (e.g. Hansen GFC, JRC TMF, MapBiomas Indonesia, or Dynamic World composites). Stage 3 accepts any pair of class-coded rasters on the same grid via `supply_shed_indicators/deforestation/configs/default.json` (paths, forest classes and oil-palm class are configurable). |
| Deforestation accuracy | Quantitative accuracy metrics (vs. an independent reference) are **not yet computed**; WorldCover 2020 (v100) and 2021 (v200) come from different algorithm versions, so part of the apparent change can be version noise. | Treat absolute areas as indicative; compare mills relative to each other; cross-check hotspots visually or against GFC/RADD. |
| Spectral confusion | Mature oil-palm canopy is confused with forest. Bias correction recodes pixels with oil-palm year-of-planting ≤ target year to class 11. | Correction was only evaluated in Indonesia/Malaysia; check before use in Africa or Latin America. |
| AGB | ESA CCI AGB: relative error < 20 % above 50 Mg ha⁻¹, ±10 Mg ha⁻¹ below; positive bias at 50–100 Mg ha⁻¹, negative bias > 250 Mg ha⁻¹ (saturation in dense tropical forest). | Shed means in high-biomass landscapes are likely underestimates. Use the SD band. |
| Fire | MCD64A1 (~500 m) misses small / low-intensity fires and fires under smoke; annual masks drop sub-annual timing; product is retrospective. | Not an early-warning system (AG-UR-07). Pair with VIIRS active fire / GLAD alerts for near-real-time use. |
| BII | PREDICTS models calibrated on Southeast-Asian studies only (1,198 sites / 38 studies for abundance). | **Not portable** without recalibration on local biodiversity data. Recent PREDICTS releases are non-commercial. |

## Supply-shed and attribution limitations

- **Probabilistic attribution.** A shed associates a mill with conditions in its likely
  sourcing area; it does not prove that a supplier of that mill caused the observed change.
- **Coverage gap.** 25 km captures 73.3 % of Danone's disclosed plantation-to-mill links
  (88.0 % at 50 km); the radius was calibrated on one company in Indonesia/Malaysia.
  Both radii are always computed so users can test sensitivity.
- **Overlapping sheds.** In dense mill regions sheds overlap heavily, so the same hectare is
  counted for several mills. Never sum per-mill areas to get a company or national total;
  dissolve the sheds first. Mills supplying several companies are attributed in full to
  each company (sourcing volumes per mill are not public).
- **Company matching.** Danone mill lists are matched to the nearest UML mill by GPS with no
  distance cap — inspect large match distances. Voluntary disclosures can change or be
  withdrawn; each release is a snapshot with its own completeness (e.g. H1-2023 plantations
  lack coordinates).
- **UML coverage** is strongest in Indonesia/Malaysia and weaker elsewhere.

## Transferability (from the D3.1 transfer tests)

| Context | Result |
|---|---|
| Nestlé supply chain (1,681 mills, UML IDs) | Ran with **no algorithmic changes** (`company/scripts/nestle/`); throughput scales. External evaluation limited because Nestlé reports a single company-wide figure with a 2015 cut-off. |
| Sarawak concessions × RSPO (248 concessions) | Deforestation logic transferred cleanly to polygons (`transferability/sarawak_rspo_concessions/`). The RSPO-vs-non-RSPO contrast is confounded by the RSPO layer (membership footprint, no certification dates). |

Transfer strengths: global, open EO inputs; commodity-agnostic buffer framework; modular
indicators that can be run independently; no in-situ calibration (except BII).

For other forest-risk commodities (soy, cattle, cocoa, rubber) replace the oil-palm
bias-correction layer with a crop-specific map, re-derive the shed radius from known
farm-to-facility links, and supply a facility list equivalent to the UML.
