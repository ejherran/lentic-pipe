# Thesis Experiment Traceability

This note supports the Chapter IV / Appendix J control table. Its purpose is to
make every model or workflow claim traceable to the dataset/freeze, split,
manifest, artifact hash, and allowed conclusion that supports it.

The generated table lives in:

- `reports/thesis/chapter_iv_evidence_matrix.csv`
- `reports/thesis/chapter_iv_evidence_matrix.md`
- `reports/thesis/chapter_iv_evidence_matrix_manifest.json`

The source configuration is:

- `configs/thesis_evidence_matrix.yaml`

Regenerate the table with:

```bash
poetry run python src/reporting/build_thesis_evidence_matrix.py
```

Interpretation rules:

- Results marked as previous-iteration evidence must not be described as final
  evaluations on the NLA-enriched freeze.
- NLA is included in the current freeze, canonical observations, panel,
  provenance, and split context.
- Under the current source-site policy, NLA is not transferred through the
  candidate NLA/WQP crosswalk to create monthly targets.
- WQP-focused post-NLA workflows are freeze-compatible and can support final
  WQP-focused conclusions, but not direct NLA target-learning claims.
- Simulation, degradation, MIFAL, and counterfactual planning rows carry their
  own scope limits and must not be upgraded to causal or official alert claims.
