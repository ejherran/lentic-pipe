# Closure V2 Eligibility Bias Report

## Decision

The development family is authorized for fitting after publication of the development lock. All ten model/seed slots pass the preregistered row and location thresholds. Incomplete rows remain in the ledger and are excluded from loss without replacement.

## Denominators

- Fit intent per model/seed: 9,413.
- Shared fit eligible per model/seed: 8,925 (0.94815680441942).
- Shared calibration eligible per model/seed: 302.
- Training shared rows/locations: 7,909 / 297.
- Model-selection shared rows/locations: 1,016 / 112.
- Calibration shared rows/locations: 302 / 58.

## Bias characterization

The registered |SMD| > 0.20 rule produced 1,190 alert rows. The largest finite absolute SMD was 1.356151; 100 rows showed complete separation and 0 were non-estimable because an observed group was absent.

The dominant structural imbalance is expected: failed sequence rows have missing serialized inputs and targets. Origin-month expert/ANFIS states were recovered from the declared development state artifacts, so state, uncertainty and delta comparisons remain estimable for all intended origins. Site coverage, series length and historical bloom-presence strata are also reported.

Exact development bloom frequency is not present in the declared outcome-free inputs; the sealed site-level `historical_bloom_presence` indicator is reported as the preregistered proxy. No target values or target-availability data were opened to manufacture a frequency measure.

## Selection diagnostic

The deterministic ridge-logistic development-only diagnostics converged for all slots: true. They are descriptive diagnostics, not a replacement cohort model and not evidence from evaluation.

## Consequence for inference

No cohort rule or threshold is changed after this audit. Closure V2 claims are restricted to the eligible subpopulation, and the registered model-specific complete-case/masked-loss sensitivities remain required when interpreting imbalance. No superiority claim is authorized by this report.

## Access boundary

Closure V1 evaluation artifacts, fresh-primary outcomes, post-2021 outcomes and observed Chl-a input lineage were not opened. Temporal model fitting was not performed.
