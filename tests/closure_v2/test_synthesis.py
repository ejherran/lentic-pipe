from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.experiments.closure_v2 import build_synthesis as synthesis


def test_allowlist_is_structured_and_excludes_sensitive_inputs() -> None:
    paths = [path.as_posix() for path in synthesis.INPUTS]
    assert paths
    assert all(Path(path).suffix in {".csv", ".json", ".yaml"} for path in paths)
    assert not any("private/FULL.md" in path or "data/targets" in path or path.endswith(".parquet") for path in paths)


def test_output_universe_is_exact() -> None:
    assert len(synthesis.TABLE_NAMES) == 14
    assert len(synthesis.FIGURE_NAMES) == 10
    assert len(synthesis.OUTPUTS) == 29
    assert len(set(synthesis.OUTPUTS)) == len(synthesis.OUTPUTS)


def test_tables_cover_registered_synthesis() -> None:
    tables = synthesis.build_tables()
    assert set(tables) == set(synthesis.TABLE_NAMES)
    assert all(not frame.empty for frame in tables.values())
    assert len(tables["T01"]) == 10
    assert set(tables["T06"]["comparison_id"]) == {"P1_vs_B2"}
    assert set(tables["T07"]["comparison_id"]) == {"P1_vs_P0"}
    assert len(tables["T11"]) == 18
    assert len(tables["T14"]) == 6


def test_fresh_primary_negative_result_is_retained() -> None:
    effects = pd.read_csv("reports/closure_v2/05_inference/pairwise_effects.csv")
    fresh = effects.loc[
        effects["evaluation_cohort"].eq("fresh_primary")
        & effects["estimand"].eq("observation_weighted")
        & effects["comparison_id"].eq("P1_vs_B2")
    ]
    assert len(fresh) == 6
    assert fresh["adjudication"].eq("inferior").all()


def test_claim_matrix_has_required_traceability() -> None:
    tables = synthesis.build_tables()
    claims = synthesis.build_claims(tables)
    assert len(claims) == 17
    assert claims["claim_id"].is_unique
    assert claims[["cohort", "estimand", "denominator", "artifact_path", "authority_commit", "limitation"]].notna().all().all()
    assert "external validation" in " ".join(claims["forbidden_wording"])


def test_final_matrix_preserves_layers_and_estimands() -> None:
    final = synthesis.build_final_matrix(synthesis.build_tables())
    assert len(final) == 162
    assert set(final["evidence_block"]) == {"inference", "degradation", "planning"}
    assert set(final["cohort"]) == {"fresh_primary", "legacy_posthoc"}
    assert final["evidence_id"].is_unique


def test_figures_are_deterministic_svg() -> None:
    tables = synthesis.build_tables()
    first = synthesis.build_figures(synthesis.PROJECT_ROOT, tables)
    second = synthesis.build_figures(synthesis.PROJECT_ROOT, tables)
    assert first == second
    assert set(first) == set(synthesis.FIGURE_NAMES)
    assert all(value.startswith(b'<svg xmlns="http://www.w3.org/2000/svg"') and value.endswith(b"</svg>\n") for value in first.values())


def test_hypothesis_verdicts_keep_v1_and_v2_separate() -> None:
    hypotheses = synthesis._hypotheses()
    assert hypotheses["hypothesis_id"].tolist() == ["H1", "H2", "H3", "H4", "H5a", "H5b"]
    h2 = hypotheses.set_index("hypothesis_id").loc["H2"]
    assert h2["v1_verdict"] == "not_estimable_primary_architecture"
    assert h2["v2_verdict"] == "estimable_negative_result"
