# MIFAL-ED/T2 Input Audit v0

Generated at UTC: `2026-06-27T17:21:42.606762+00:00`
Panel: `data/panel/panel_monthly_v0.parquet`
Splits: `data/splits/monthly_model_splits_v0.parquet`
Audit rows: `18,000`
Horizons: `1, 2, 3`
Evaluation splits: `train, validation, test`

This is an input-availability audit, not a MIFAL performance evaluation.

## Gate Decision

- Complete recommended minimum surface: `False`
- Observed minimum variables: `Chl, Secchi, TP, Tw`
- Missing minimum variables: `Wind`
- Recommended next gate: `build_mifal_observable_minimal_adapter`

The first empirical MIFAL variant should use the observable panel inputs and represent unavailable drivers through priors and low reliability, rather than fabricating hydrodynamic or meteorological covariates.

## Overall Variable Coverage

| MIFAL variable | role | status | found columns | rows | present rows | coverage | note |
|---|---|---|---|---:|---:|---:|---|
| `Tw` | `minimum_temperature` | `direct_observable` | `mean_temperature_C` | 18,000 | 3,494 | 0.1941 | Origin-month water temperature maps directly to MIFAL water temperature. |
| `TP` | `minimum_nutrients` | `direct_observable` | `mean_TP_ugL` | 18,000 | 4,645 | 0.2581 | Total phosphorus maps directly to MIFAL TP. |
| `TN` | `optional_nutrients` | `unit_transform_observable` | `mean_TN_ugL` | 18,000 | 2,482 | 0.1379 | Adapter must divide by 1000 before passing TN to MIFAL. |
| `Secchi` | `minimum_light` | `direct_observable` | `mean_secchi_depth_m` | 18,000 | 5,412 | 0.3007 | Secchi depth maps directly to transparency/light availability. |
| `Turb` | `light_support` | `direct_observable` | `mean_turbidity_NTU` | 18,000 | 1,859 | 0.1033 | Turbidity can support light limitation when Secchi is absent. |
| `DOb` | `optional_internal_loading` | `qualified_observable` | `mean_DO_mgL` | 18,000 | 2,924 | 0.1624 | Panel DO is not guaranteed to be bottom oxygen; treat as qualified evidence unless depth policy is added. |
| `Chl` | `minimum_biological_observation` | `direct_observable` | `mean_chlorophyll_a_ugL` | 18,000 | 17,449 | 0.9694 | Origin-month Chl-a can assimilate the analysis state before forecasting. |
| `Chl_prev` | `minimum_biological_memory` | `constructible_from_origin` | `mean_chlorophyll_a_ugL` | 18,000 | 17,449 | 0.9694 | First adapter can seed biological memory from origin-month Chl-a; later versions should audit explicit lags. |
| `Wind` | `minimum_hydrodynamics` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | No wind or mixing column is present in the current frozen monthly panel. |
| `Residence` | `optional_hydrodynamics` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | No lake-specific residence-time column is present in the current frozen monthly panel. |
| `Flushing` | `optional_hydrodynamics` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | No flushing-rate column is present in the current frozen monthly panel. |
| `Strat` | `optional_hydrodynamics` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | No stratification index is present in the current frozen monthly panel. |
| `Phyco` | `optional_biological_proxy` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | Phyco signals were reserved for future extension and are not in the current canonical panel. |
| `Sat` | `optional_spatial_bloom_proxy` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | Satellite bloom index is not in the current frozen monthly panel. |
| `Visual` | `optional_qualitative_bloom_proxy` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | Visual bloom reports are not in the current frozen monthly panel. |
| `Rain` | `optional_runoff` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | Recent precipitation is not in the current frozen monthly panel. |
| `LandLoad` | `optional_runoff` | `unavailable_in_freeze` | `none` | 18,000 | 0 | 0.0000 | Land-load/runoff pressure is not in the current frozen monthly panel. |

## Coverage By Split

| split | horizon | MIFAL variable | rows | present rows | coverage |
|---|---:|---|---:|---:|---:|
| `test` | 1 | `Tw` | 2,000 | 507 | 0.2535 |
| `test` | 1 | `TP` | 2,000 | 787 | 0.3935 |
| `test` | 1 | `TN` | 2,000 | 436 | 0.2180 |
| `test` | 1 | `Secchi` | 2,000 | 777 | 0.3885 |
| `test` | 1 | `Turb` | 2,000 | 250 | 0.1250 |
| `test` | 1 | `DOb` | 2,000 | 419 | 0.2095 |
| `test` | 1 | `Chl` | 2,000 | 1,927 | 0.9635 |
| `test` | 1 | `Wind` | 2,000 | 0 | 0.0000 |
| `test` | 2 | `Tw` | 2,000 | 502 | 0.2510 |
| `test` | 2 | `TP` | 2,000 | 784 | 0.3920 |
| `test` | 2 | `TN` | 2,000 | 454 | 0.2270 |
| `test` | 2 | `Secchi` | 2,000 | 774 | 0.3870 |
| `test` | 2 | `Turb` | 2,000 | 298 | 0.1490 |
| `test` | 2 | `DOb` | 2,000 | 425 | 0.2125 |
| `test` | 2 | `Chl` | 2,000 | 1,927 | 0.9635 |
| `test` | 2 | `Wind` | 2,000 | 0 | 0.0000 |
| `test` | 3 | `Tw` | 2,000 | 458 | 0.2290 |
| `test` | 3 | `TP` | 2,000 | 762 | 0.3810 |
| `test` | 3 | `TN` | 2,000 | 463 | 0.2315 |
| `test` | 3 | `Secchi` | 2,000 | 748 | 0.3740 |
| `test` | 3 | `Turb` | 2,000 | 326 | 0.1630 |
| `test` | 3 | `DOb` | 2,000 | 418 | 0.2090 |
| `test` | 3 | `Chl` | 2,000 | 1,924 | 0.9620 |
| `test` | 3 | `Wind` | 2,000 | 0 | 0.0000 |
| `train` | 1 | `Tw` | 2,000 | 316 | 0.1580 |
| `train` | 1 | `TP` | 2,000 | 269 | 0.1345 |
| `train` | 1 | `TN` | 2,000 | 70 | 0.0350 |
| `train` | 1 | `Secchi` | 2,000 | 506 | 0.2530 |
| `train` | 1 | `Turb` | 2,000 | 129 | 0.0645 |
| `train` | 1 | `DOb` | 2,000 | 262 | 0.1310 |
| `train` | 1 | `Chl` | 2,000 | 1,960 | 0.9800 |
| `train` | 1 | `Wind` | 2,000 | 0 | 0.0000 |
| `train` | 2 | `Tw` | 2,000 | 309 | 0.1545 |
| `train` | 2 | `TP` | 2,000 | 237 | 0.1185 |
| `train` | 2 | `TN` | 2,000 | 89 | 0.0445 |
| `train` | 2 | `Secchi` | 2,000 | 518 | 0.2590 |
| `train` | 2 | `Turb` | 2,000 | 124 | 0.0620 |
| `train` | 2 | `DOb` | 2,000 | 247 | 0.1235 |
| `train` | 2 | `Chl` | 2,000 | 1,963 | 0.9815 |
| `train` | 2 | `Wind` | 2,000 | 0 | 0.0000 |
| `train` | 3 | `Tw` | 2,000 | 298 | 0.1490 |
| `train` | 3 | `TP` | 2,000 | 200 | 0.1000 |
| `train` | 3 | `TN` | 2,000 | 70 | 0.0350 |
| `train` | 3 | `Secchi` | 2,000 | 510 | 0.2550 |
| `train` | 3 | `Turb` | 2,000 | 158 | 0.0790 |
| `train` | 3 | `DOb` | 2,000 | 267 | 0.1335 |
| `train` | 3 | `Chl` | 2,000 | 1,956 | 0.9780 |
| `train` | 3 | `Wind` | 2,000 | 0 | 0.0000 |
| `validation` | 1 | `Tw` | 2,000 | 418 | 0.2090 |
| `validation` | 1 | `TP` | 2,000 | 563 | 0.2815 |
| `validation` | 1 | `TN` | 2,000 | 300 | 0.1500 |
| `validation` | 1 | `Secchi` | 2,000 | 572 | 0.2860 |
| `validation` | 1 | `Turb` | 2,000 | 185 | 0.0925 |
| `validation` | 1 | `DOb` | 2,000 | 319 | 0.1595 |
| `validation` | 1 | `Chl` | 2,000 | 1,948 | 0.9740 |
| `validation` | 1 | `Wind` | 2,000 | 0 | 0.0000 |
| `validation` | 2 | `Tw` | 2,000 | 339 | 0.1695 |
| `validation` | 2 | `TP` | 2,000 | 522 | 0.2610 |
| `validation` | 2 | `TN` | 2,000 | 296 | 0.1480 |
| `validation` | 2 | `Secchi` | 2,000 | 510 | 0.2550 |
| `validation` | 2 | `Turb` | 2,000 | 183 | 0.0915 |
| `validation` | 2 | `DOb` | 2,000 | 273 | 0.1365 |
| `validation` | 2 | `Chl` | 2,000 | 1,925 | 0.9625 |
| `validation` | 2 | `Wind` | 2,000 | 0 | 0.0000 |
| `validation` | 3 | `Tw` | 2,000 | 347 | 0.1735 |
| `validation` | 3 | `TP` | 2,000 | 521 | 0.2605 |
| `validation` | 3 | `TN` | 2,000 | 304 | 0.1520 |
| `validation` | 3 | `Secchi` | 2,000 | 497 | 0.2485 |
| `validation` | 3 | `Turb` | 2,000 | 206 | 0.1030 |
| `validation` | 3 | `DOb` | 2,000 | 294 | 0.1470 |
| `validation` | 3 | `Chl` | 2,000 | 1,919 | 0.9595 |
| `validation` | 3 | `Wind` | 2,000 | 0 | 0.0000 |

## Outputs

- Summary: `reports/mifal/mifal_input_audit_smoke_summary.csv`
- By split: `reports/mifal/mifal_input_audit_smoke_by_split.csv`
- By source: `reports/mifal/mifal_input_audit_smoke_by_source.csv`
- Manifest: `reports/mifal/mifal_input_audit_smoke_manifest.json`
