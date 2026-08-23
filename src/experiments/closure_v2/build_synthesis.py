"""Build the deterministic, structured-only Closure V2 thesis synthesis."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUTHORITY_COMMIT = "e85990193ce2c97cbf7b2f200e8320fa05bbe5ac"
V1_TAG_COMMIT = "eb07598aa54a0944d1a87fe46d62415d0a4454aa"
SCRIPT_PATH = Path("src/experiments/closure_v2/build_synthesis.py")
TEST_PATH = Path("tests/closure_v2/test_synthesis.py")
OUTPUT_ROOT = Path("reports/closure_v2/08_synthesis")
TABLE_ROOT = OUTPUT_ROOT / "THESIS_TABLES"
FIGURE_ROOT = OUTPUT_ROOT / "THESIS_FIGURES"
REPORT = OUTPUT_ROOT / "FINAL_CLOSURE_REPORT.md"
FINAL_MATRIX = OUTPUT_ROOT / "FINAL_CLOSURE_MATRIX.csv"
CLAIM_MATRIX = OUTPUT_ROOT / "THESIS_CLAIM_EVIDENCE_MATRIX.csv"
CHANGE_MAP = OUTPUT_ROOT / "MANUSCRIPT_CHANGE_MAP.md"
MANIFEST = OUTPUT_ROOT / "synthesis_manifest.json"

TABLE_NAMES = {
    "T01": "T01_model_availability.csv",
    "T02": "T02_fit_eligibility_attrition.csv",
    "T03": "T03_eligibility_bias.csv",
    "T04": "T04_benchmark_observation_weighted.csv",
    "T05": "T05_benchmark_site_weighted.csv",
    "T06": "T06_p1_vs_b2_inference.csv",
    "T07": "T07_p1_vs_p0_inference.csv",
    "T08": "T08_threshold_sensitivity.csv",
    "T09": "T09_uncertainty.csv",
    "T10": "T10_degradation_m0_p1.csv",
    "T11": "T11_planning.csv",
    "T12": "T12_v1_v2_evidence_boundary.csv",
    "T13": "T13_software_evidence.csv",
    "T14": "T14_hypothesis_adjudication.csv",
}
FIGURE_NAMES = {
    "F01": "F01_fit_eligibility_funnel.svg",
    "F02": "F02_eligibility_bias.svg",
    "F03": "F03_training_curves.svg",
    "F04": "F04_benchmark_metrics_availability.svg",
    "F05": "F05_paired_effects.svg",
    "F06": "F06_calibration_uncertainty.svg",
    "F07": "F07_degradation_curves.svg",
    "F08": "F08_planning_effects.svg",
    "F09": "F09_v1_v2_provenance.svg",
    "F10": "F10_hypothesis_verdicts.svg",
}

SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
TRAINING_CURVES = tuple(
    Path(f"reports/closure_v2/02_models/{model}/seed_{seed}/training_curve.csv")
    for model in ("P0", "P1") for seed in SEEDS
)
INPUTS = (
    Path("configs/closure_v2/analysis_plan.yaml"),
    Path("reports/closure_v2/00_protocol/protocol_lock.json"),
    Path("reports/closure_v2/00_protocol/model_lock.json"),
    Path("reports/closure_v2/00_protocol/v1_reference_manifest.json"),
    Path("reports/closure_v2/01_surface/eligibility_manifest.json"),
    Path("reports/closure_v2/01_surface/eligibility_counts.csv"),
    Path("reports/closure_v2/01_surface/eligibility_covariate_balance.csv"),
    Path("reports/closure_v2/01_surface/eligibility_model_diagnostics.csv"),
    Path("reports/closure_v2/01_surface/locked_evaluation_input_manifest.json"),
    Path("reports/closure_v2/02_models/family_manifest.json"),
    Path("reports/closure_v2/02_models/family_summary.csv"),
    *TRAINING_CURVES,
    Path("reports/closure_v2/03_calibration/calibration_manifest.json"),
    Path("reports/closure_v2/03_calibration/model_availability.csv"),
    Path("reports/closure_v2/03_calibration/calibration_metrics.csv"),
    Path("reports/closure_v2/04_evaluation/evaluation_manifest.json"),
    Path("reports/closure_v2/04_evaluation/intent_to_predict_funnel.csv"),
    Path("reports/closure_v2/04_evaluation/model_metrics_long.csv"),
    Path("reports/closure_v2/04_evaluation/threshold_sensitivity.csv"),
    Path("reports/closure_v2/04_evaluation/uncertainty_ledger.csv"),
    Path("reports/closure_v2/05_inference/inference_manifest.json"),
    Path("reports/closure_v2/05_inference/pairwise_effects.csv"),
    Path("reports/closure_v2/05_inference/multiplicity_report.csv"),
    Path("reports/closure_v2/06_degradation/degradation_manifest.json"),
    Path("reports/closure_v2/06_degradation/aupd.csv"),
    Path("reports/closure_v2/06_degradation/pairwise_effects.csv"),
    Path("reports/closure_v2/07_planning/planning_manifest.json"),
    Path("reports/closure_v2/07_planning/planning_bootstrap.csv"),
    Path("reports/closure_v2/07_planning/ecological_coherence.csv"),
    Path("reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv"),
    Path("reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv"),
    Path("reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json"),
)
OUTPUTS = (
    FINAL_MATRIX, CLAIM_MATRIX, REPORT, CHANGE_MAP,
    *(TABLE_ROOT / name for name in TABLE_NAMES.values()),
    *(FIGURE_ROOT / name for name in FIGURE_NAMES.values()),
    MANIFEST,
)
PREEXECUTION_IMPLEMENTATION_PATHS = {SCRIPT_PATH.as_posix(), TEST_PATH.as_posix()}


class SynthesisError(RuntimeError):
    """Raised when the sealed synthesis contract or an input drifts."""


def _run_git(*args: str, root: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise SynthesisError(f"Required regular file is absent: {relative}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads(_require_regular(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SynthesisError(f"JSON root is not an object: {relative}")
    return cast(dict[str, Any], value)


def _yaml(root: Path, relative: Path) -> dict[str, Any]:
    value = yaml.safe_load(_require_regular(root, relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SynthesisError(f"YAML root is not a mapping: {relative}")
    return cast(dict[str, Any], value)


def _csv(root: Path, relative: str) -> pd.DataFrame:
    return pd.read_csv(_require_regular(root, Path(relative)))


def _record(root: Path, relative: Path, role: str) -> dict[str, Any]:
    path = _require_regular(root, relative)
    return {
        "path": relative.as_posix(), "role": role,
        "bytes": path.stat().st_size, "sha256": _sha256(path),
    }


def _payload_record(relative: Path, payload: bytes, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(), "role": role, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _verify_manifest_records(root: Path, relative: Path) -> dict[str, Any]:
    manifest = _json(root, relative)
    if manifest.get("status") != "completed" or manifest.get("manifest_written_last") is not True:
        raise SynthesisError(f"Terminal manifest is not completed/manifest-last: {relative}")
    for section in ("inputs", "outputs"):
        records = manifest.get(section, [])
        if not isinstance(records, list):
            raise SynthesisError(f"Malformed manifest records: {relative}/{section}")
        for raw in records:
            if not isinstance(raw, Mapping) or "path" not in raw or "sha256" not in raw:
                continue
            path = _require_regular(root, Path(str(raw["path"])))
            if _sha256(path) != raw["sha256"] or path.stat().st_size != raw.get("bytes"):
                raise SynthesisError(f"Manifest binding drifted: {relative} -> {raw['path']}")
    return manifest


def validate_authority(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _run_git("rev-parse", "HEAD", root=root)
    remote = _run_git("rev-parse", "origin/closure-v2", root=root)
    v1_tag = _run_git("rev-parse", "thesis-closure-v1^{}", root=root)
    if head != AUTHORITY_COMMIT or remote != head or v1_tag != V1_TAG_COMMIT:
        raise SynthesisError("P16 publication, tracking ref, or immutable V1 tag drifted")
    status = _run_git("status", "--porcelain=v1", "--untracked-files=all", root=root)
    changed = {line[3:] for line in status.splitlines() if line}
    if changed - PREEXECUTION_IMPLEMENTATION_PATHS:
        raise SynthesisError(f"Unexpected P17 pre-execution paths: {sorted(changed)}")
    if any((root / path).exists() or (root / path).is_symlink() for path in OUTPUTS):
        raise SynthesisError("A P17 synthesis output already exists")
    for relative in INPUTS:
        path = _require_regular(root, relative)
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"], cwd=root,
            check=True, capture_output=True,
        ).stdout
        if path.read_bytes() != blob:
            raise SynthesisError(f"Allowlisted input differs from published Git blob: {relative}")
    plan = _yaml(root, Path("configs/closure_v2/analysis_plan.yaml"))
    boundaries = cast(Mapping[str, Any], plan.get("claim_boundaries", {}))
    if boundaries.get("field_causality") != "forbidden" or boundaries.get("official_recommendations") != "forbidden":
        raise SynthesisError("Claim boundaries drifted")
    terminal_paths = (
        Path("reports/closure_v2/01_surface/eligibility_manifest.json"),
        Path("reports/closure_v2/02_models/family_manifest.json"),
        Path("reports/closure_v2/03_calibration/calibration_manifest.json"),
        Path("reports/closure_v2/04_evaluation/evaluation_manifest.json"),
        Path("reports/closure_v2/05_inference/inference_manifest.json"),
        Path("reports/closure_v2/06_degradation/degradation_manifest.json"),
        Path("reports/closure_v2/07_planning/planning_manifest.json"),
    )
    manifests = [_verify_manifest_records(root, path) for path in terminal_paths]
    phases = [manifests[index].get("phase") for index in range(3, 7)]
    if phases != ["P13", "P14", "P15", "P16"]:
        raise SynthesisError(f"Terminal result phase chain drifted: {phases}")
    availability = _csv(root, "reports/closure_v2/03_calibration/model_availability.csv")
    if len(availability) != 10 or not availability["status"].eq("available").all() or availability["replacement_used"].astype(bool).any():
        raise SynthesisError("P0/P1 five-slot availability drifted")
    evaluation = manifests[3]
    if evaluation.get("evaluation_cohorts") != {"fresh_primary": 2286, "legacy_posthoc": 4488} or evaluation.get("legacy_and_fresh_pooled") is not False:
        raise SynthesisError("Evaluation cohort contract drifted")
    planning = manifests[-1]
    if planning.get("evaluation_cohorts") != ["legacy_posthoc", "fresh_primary"] or planning.get("holm_universe_size") != 9:
        raise SynthesisError("Planning cohort or Holm universe drifted")
    return {
        "status": "ready_for_structured_synthesis", "head": head,
        "v1_tag_commit": v1_tag, "allowlisted_input_count": len(INPUTS),
        "terminal_manifest_count": len(terminal_paths), "output_count": len(OUTPUTS),
        "fresh_primary_origins": 2286, "legacy_posthoc_origins": 4488,
        "raw_targets_read": False, "parquet_read": False, "private_full_read": False,
        "metrics_recomputed": False, "models_recomputed": False,
    }


def _add_context(frame: pd.DataFrame, artifact: str, limitation: str) -> pd.DataFrame:
    out = frame.copy()
    out["artifact_path"] = artifact
    out["authority_commit"] = AUTHORITY_COMMIT
    out["limitation"] = limitation
    return out


def _hypotheses() -> pd.DataFrame:
    rows = [
        ("H1", "limited_descriptive_support", "not_supported_on_fresh_primary", "fresh_primary", "Adaptive ANFIS state did not improve P1 over P0: Brier was inconclusive and PR-AUC inferior at h1-h3.", "966;933;885 shared rows", "V2 tests predictive utility of the adaptive state, not interpretability, membership stability, or saturation."),
        ("H2", "not_estimable_primary_architecture", "estimable_negative_result", "fresh_primary", "P1 was inferior to B2 for observation-weighted Brier and PR-AUC at h1-h3.", "966;933;885 shared rows", "Internal evaluation on unused WQP monitoring locations; no external validation."),
        ("H3", "partial_descriptive_only", "partial_descriptive_support", "fresh_primary", "Uncertainty and simulated degradation became estimable, with model/scenario-specific results rather than a global guarantee.", "published rows by model, horizon and scenario", "Simulated missingness is not field robustness and intervals are not universal calibration."),
        ("H4", "not_estimable", "estimable_descriptive_contrast", "fresh_primary", "M0-P1 degradation contrasts were estimated on identical masks; no universal crossover was found.", "registered family rows", "M0 is a robustness comparator, not a causal mechanism or field intervention."),
        ("H5a", "not_confirmed_scientifically", "not_supported", "fresh_primary", "All nine planning objectives had negative clustered estimates versus no_action after registered cost/support penalties.", "9 actions; 6,858 intended rows each", "Raw-proxy simulation does not authorize causality, official recommendations, or universal optima."),
        ("H5b", "not_estimable", "not_estimable_registered_scope", "not_applicable", "A separate field net-benefit endpoint was not registered or observed.", "9-action planning family", "delta_objective_vs_no_action is a simulated objective, not observed net benefit."),
    ]
    return pd.DataFrame(rows, columns=[
        "hypothesis_id", "v1_verdict", "v2_verdict", "cohort",
        "evidence_summary", "denominator", "limitation",
    ]).assign(
        decisive_artifact="reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv",
        authority_commit=AUTHORITY_COMMIT,
    )


def build_tables(root: Path = PROJECT_ROOT) -> dict[str, pd.DataFrame]:
    availability = _csv(root, "reports/closure_v2/03_calibration/model_availability.csv")
    eligibility = _csv(root, "reports/closure_v2/01_surface/eligibility_counts.csv")
    balance = _csv(root, "reports/closure_v2/01_surface/eligibility_covariate_balance.csv")
    diagnostics = _csv(root, "reports/closure_v2/01_surface/eligibility_model_diagnostics.csv")
    metrics = _csv(root, "reports/closure_v2/04_evaluation/model_metrics_long.csv")
    threshold = _csv(root, "reports/closure_v2/04_evaluation/threshold_sensitivity.csv")
    uncertainty = _csv(root, "reports/closure_v2/04_evaluation/uncertainty_ledger.csv")
    effects = _csv(root, "reports/closure_v2/05_inference/pairwise_effects.csv")
    aupd = _csv(root, "reports/closure_v2/06_degradation/aupd.csv")
    planning = _csv(root, "reports/closure_v2/07_planning/planning_bootstrap.csv")
    v1_matrix = _csv(root, "reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv")

    t01 = _add_context(availability, "reports/closure_v2/03_calibration/model_availability.csv", "Five seeds are algorithmic slots, not ecological replicates.")
    t02 = _add_context(eligibility, "reports/closure_v2/01_surface/eligibility_counts.csv", "Claims apply to the complete-case shared-fit population; all incomplete intent rows remain counted.")
    bias = balance.groupby(["model_id", "base_seed"], sort=True).agg(
        compared_cells=("abs_smd", "size"), max_abs_smd=("abs_smd", "max"),
        flagged_cells=("alert", "sum"),
    ).reset_index()
    diag = diagnostics.groupby(["model_id", "base_seed"], sort=True).agg(
        fit_rows=("rows", "first"), eligible_rows=("eligible_rows", "first"),
        noneligible_rows=("noneligible_rows", "first"), converged=("converged", "all"),
        roc_auc_descriptive=("roc_auc_descriptive", "first"),
    ).reset_index()
    t03 = _add_context(bias.merge(diag, on=["model_id", "base_seed"], validate="one_to_one"), "reports/closure_v2/01_surface/eligibility_covariate_balance.csv|reports/closure_v2/01_surface/eligibility_model_diagnostics.csv", "Eligibility diagnostics are descriptive and do not repair selection bias.")
    selected_metrics = metrics.loc[
        metrics["aggregation_level"].eq("family")
        & metrics["metric"].isin(["brier", "pr_auc", "f2", "ece10"])
    ].copy()
    t04 = _add_context(selected_metrics.loc[selected_metrics["estimand"].eq("observation_weighted")], "reports/closure_v2/04_evaluation/model_metrics_long.csv", "Models are compared only within cohort, estimand, horizon and evaluable denominator.")
    t05 = _add_context(selected_metrics.loc[selected_metrics["estimand"].eq("site_weighted")], "reports/closure_v2/04_evaluation/model_metrics_long.csv", "Site-weighted estimates are not pooled with observation-weighted estimates.")
    t06 = _add_context(effects.loc[effects["comparison_id"].eq("P1_vs_B2")], "reports/closure_v2/05_inference/pairwise_effects.csv", "Fresh-primary is internal WQP evidence; legacy-posthoc is retrospective complementary evidence.")
    t07 = _add_context(effects.loc[effects["comparison_id"].eq("P1_vs_P0")], "reports/closure_v2/05_inference/pairwise_effects.csv", "P0 and P1 share fit keys and budget; mixed or inferior results remain explicit.")
    t08 = _add_context(threshold, "reports/closure_v2/04_evaluation/threshold_sensitivity.csv", "Predeclared sensitivity only; thresholds were not recalibrated after evaluation.")
    t09 = _add_context(uncertainty.loc[uncertainty["aggregation_level"].eq("family")], "reports/closure_v2/04_evaluation/uncertainty_ledger.csv", "Coverage is model/cohort/horizon specific and not a universal calibration guarantee.")
    t10 = _add_context(aupd.loc[aupd["aggregation_level"].eq("family_mean_over_registered_seeds")], "reports/closure_v2/06_degradation/aupd.csv", "Robustness is under deterministic simulated missingness, not field missingness.")
    t11 = _add_context(planning, "reports/closure_v2/07_planning/planning_bootstrap.csv", "Simulated raw-proxy objectives are not causal effects, recommendations, or universal optima.")
    t12 = pd.DataFrame([
        {"evidence_version": "V1", "layer": "frozen", "state": "immutable_published_evidence", "row_count": len(v1_matrix), "authority": "ea8ddce7f8edb9a61db97e29178e52603fa371b1", "allowed_wording": "Closure V1 result at its published authority", "forbidden_wording": "retroactive V2 correction"},
        {"evidence_version": "V2", "layer": "legacy_posthoc", "state": "retrospective_complementary", "row_count": 4488, "authority": AUTHORITY_COMMIT, "allowed_wording": "retrospective complementary analysis", "forbidden_wording": "new confirmation or prospective validation"},
        {"evidence_version": "V2", "layer": "fresh_primary", "state": "internal_unused_wqp_locations", "row_count": 2286, "authority": AUTHORITY_COMMIT, "allowed_wording": "internal evaluation on WQP monitoring locations unused by V1", "forbidden_wording": "external validation or unseen waterbodies"},
        {"evidence_version": "V2", "layer": "software", "state": "reproducible_artifact_evidence", "row_count": 7, "authority": AUTHORITY_COMMIT, "allowed_wording": "reproducible software evidence", "forbidden_wording": "scientific efficacy certification"},
    ])
    terminal = [
        ("protocol", "reports/closure_v2/00_protocol/protocol_lock.json"),
        ("model_lock", "reports/closure_v2/00_protocol/model_lock.json"),
        ("eligibility", "reports/closure_v2/01_surface/eligibility_manifest.json"),
        ("training", "reports/closure_v2/02_models/family_manifest.json"),
        ("calibration", "reports/closure_v2/03_calibration/calibration_manifest.json"),
        ("evaluation", "reports/closure_v2/04_evaluation/evaluation_manifest.json"),
        ("inference", "reports/closure_v2/05_inference/inference_manifest.json"),
        ("degradation", "reports/closure_v2/06_degradation/degradation_manifest.json"),
        ("planning", "reports/closure_v2/07_planning/planning_manifest.json"),
    ]
    t13 = pd.DataFrame([
        {"component": component, "artifact_path": path, "sha256": _sha256(root / path), "bytes": (root / path).stat().st_size, "status": _json(root, Path(path)).get("status", "locked"), "authority_commit": AUTHORITY_COMMIT, "limitation": "Artifact integrity and reproducibility do not demonstrate scientific efficacy."}
        for component, path in terminal
    ])
    t14 = _hypotheses()
    tables = {key: value.reset_index(drop=True) for key, value in {
        "T01": t01, "T02": t02, "T03": t03, "T04": t04, "T05": t05,
        "T06": t06, "T07": t07, "T08": t08, "T09": t09, "T10": t10,
        "T11": t11, "T12": t12, "T13": t13, "T14": t14,
    }.items()}
    if set(tables) != set(TABLE_NAMES) or any(frame.empty for frame in tables.values()):
        raise SynthesisError("The 14-table synthesis universe is incomplete")
    return tables


def _claim(
    claim_id: str, chapter: str, section: str, claim_text: str, claim_status: str,
    cohort: str, estimand: str, artifact_path: str, row_filter: str, metric: str,
    value: str, denominator: str, limitation: str, allowed: str, forbidden: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id, "chapter": chapter, "section": section,
        "claim_text": claim_text, "claim_status": claim_status, "cohort": cohort,
        "estimand": estimand, "artifact_path": artifact_path, "row_filter": row_filter,
        "metric": metric, "value": value, "denominator": denominator,
        "authority_commit": AUTHORITY_COMMIT, "limitation": limitation,
        "allowed_wording": allowed, "forbidden_wording": forbidden,
    }


def build_claims(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    fresh = tables["T06"].loc[
        tables["T06"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T06"]["estimand"].eq("observation_weighted")
    ]
    p0 = tables["T07"].loc[
        tables["T07"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T07"]["estimand"].eq("observation_weighted")
    ]
    planning = tables["T11"].loc[tables["T11"]["evaluation_cohort"].eq("fresh_primary")]
    values_b2 = "|".join(f"h{int(r.horizon_months)}:{r.metric}:{r.adjudication}:{r.estimate:.6f}" for r in fresh.itertuples())
    values_p0 = "|".join(f"h{int(r.horizon_months)}:{r.metric}:{r.adjudication}:{r.estimate:.6f}" for r in p0.itertuples())
    plan_values = "|".join(f"{r.scenario_id}:{r.estimate:.6f}" for r in planning.itertuples())
    rows = [
        _claim("C01_fresh_surface", "III", "Evaluation surface", "V2 evaluated 2,286 origins from 137 WQP monitoring locations unused by V1.", "confirmatory_available", "fresh_primary", "intent_to_predict", "reports/closure_v2/01_surface/locked_evaluation_input_manifest.json", "evaluation_cohort=fresh_primary", "location/origin counts", "137;2286", "6,858 origin-horizon attempts", "Internal WQP monitoring locations, not external or unseen-waterbody validation.", "internal evaluation on WQP monitoring locations unused by V1", "external validation; unseen waterbodies"),
        _claim("C02_legacy_surface", "III", "Evaluation surface", "The 88 V1 holdout locations were reused only as retrospective complementary evidence.", "posthoc_available", "legacy_posthoc", "intent_to_predict", "reports/closure_v2/04_evaluation/evaluation_manifest.json", "evaluation_cohort=legacy_posthoc", "origin count", "4488", "13,464 origin-horizon attempts", "Outcomes were previously opened in V1.", "retrospective complementary analysis", "new confirmation; prospective validation"),
        _claim("C03_shared_fit", "III", "Eligibility", "P0 and P1 used the same 8,925 complete-case fit rows for every registered seed.", "descriptive_available", "development", "complete_case_shared_fit", "reports/closure_v2/01_surface/eligibility_counts.csv", "all model_id/base_seed rows", "shared_fit_eligible_rows", "8925", "9,413 fit-intent rows; 9,732 total intent origins", "Claims are conditional on the eligible development subpopulation.", "exact shared complete-case fit", "all intended rows entered model loss"),
        _claim("C04_model_availability", "IV", "Model availability", "All five P0 and five P1 slots were trained and calibrated without replacement.", "confirmatory_available", "development", "registered_seed_family", "reports/closure_v2/03_calibration/model_availability.csv", "status=available", "available model slots", "10/10", "5 P0 plus 5 P1 slots", "Seeds are algorithmic slots, not ecological replicates.", "five registered slots per family", "five independent ecological replications"),
        _claim("C05_p1_vs_b2", "IV", "Primary benchmark", "P1 was inferior to B2 for observation-weighted Brier and PR-AUC at h1-h3 on fresh-primary.", "confirmatory_available", "fresh_primary", "observation_weighted", "reports/closure_v2/05_inference/pairwise_effects.csv", "comparison_id=P1_vs_B2; cohort=fresh_primary; estimand=observation_weighted", "paired Brier/PR-AUC difference", values_b2, "966|933|885 shared rows", "Internal fresh WQP evidence only; no universal model ranking.", "P1 was inferior on the registered fresh-primary contrasts", "P1 is universally inferior; external validation"),
        _claim("C06_p1_vs_p0", "IV", "Primary benchmark", "Against P0 on fresh-primary, P1 Brier was inconclusive and P1 PR-AUC was inferior at h1-h3.", "confirmatory_available", "fresh_primary", "observation_weighted", "reports/closure_v2/05_inference/pairwise_effects.csv", "comparison_id=P1_vs_P0; cohort=fresh_primary; estimand=observation_weighted", "paired Brier/PR-AUC difference", values_p0, "966|933|885 shared rows", "This tests predictive utility of adaptive state, not interpretability or equivalence.", "no fresh-primary advantage for P1 over P0", "P0 and P1 are equivalent; ANFIS is uninterpretable"),
        _claim("C07_legacy_p1_p0", "IV", "Complementary benchmark", "P1 was descriptively favorable to P0 in the legacy-posthoc layer.", "posthoc_available", "legacy_posthoc", "observation_weighted and site_weighted", "reports/closure_v2/05_inference/pairwise_effects.csv", "comparison_id=P1_vs_P0; cohort=legacy_posthoc", "paired Brier/PR-AUC difference", "favorable in 12/12 rows", "published shared-success rows/clusters per row", "Retrospective evidence cannot overturn the fresh-primary negative result.", "retrospective complementary favorable contrast", "independent confirmation"),
        _claim("C08_thresholds", "IV", "Sensitivity", "Results were reported at predeclared 25, 30, 33 and 50 ug/L cutoffs without recalibration.", "descriptive_available", "fresh_primary|legacy_posthoc", "separate by cohort", "reports/closure_v2/04_evaluation/threshold_sensitivity.csv", "all rows", "threshold sensitivity", "25;30;33;50", "rows published per model/horizon/cutoff", "Thresholds are project endpoints, not official ecological standards.", "predeclared threshold sensitivity", "official threshold recommendation"),
        _claim("C09_uncertainty", "IV", "Uncertainty", "Interval diagnostics are available by model, cohort and horizon.", "descriptive_available", "fresh_primary|legacy_posthoc", "separate observation/site estimands", "reports/closure_v2/04_evaluation/uncertainty_ledger.csv", "aggregation_level=family", "PICP/MPIW/Winkler", "model-specific", "rows and locations published per row", "No global calibration guarantee follows.", "model/cohort/horizon-specific interval diagnostics", "universally calibrated uncertainty"),
        _claim("C10_degradation", "IV", "Robustness", "M0-P1 degradation became estimable on identical deterministic masks without a universal crossover.", "descriptive_available", "fresh_primary|legacy_posthoc", "separate by cohort and estimand", "reports/closure_v2/06_degradation/pairwise_effects.csv", "aggregation_level=family_mean_over_registered_seeds", "AUPD and paired degradation effects", "estimable; no universal crossover", "registered scenario/horizon rows", "Only simulated missingness was evaluated.", "robustness under simulated missingness", "field robustness guarantee"),
        _claim("C11_planning", "IV", "Planning", "No registered planning action exceeded no_action on the fresh-primary objective after cost/support penalties.", "confirmatory_available", "fresh_primary", "observation_weighted_pooled_h1_h3", "reports/closure_v2/07_planning/planning_bootstrap.csv", "evaluation_cohort=fresh_primary", "delta_objective_vs_no_action", plan_values, "9 actions; 6,858 intended rows/action", "Raw-proxy simulation is not causal decision evidence.", "no positive evidence for the simulated planning objective", "no action works; official recommendation; causal effect"),
        _claim("C12_v1_boundary", "V", "Evidence provenance", "Closure V1 remains immutable and V2 does not retroactively replace its unavailable P0/P1 result.", "descriptive_available", "V1_frozen|V2_additive", "not_applicable", "reports/closure_v2/08_synthesis/THESIS_TABLES/T12_v1_v2_evidence_boundary.csv", "all rows", "evidence boundary", "V1 frozen; V2 additive", "130 V1 closure rows plus V2 evidence", "Results belong to different freezes and surfaces.", "V2 resolves a new additive experiment", "V1 secretly trained P0/P1; retroactive correction"),
        _claim("C13_gru_wording", "V", "Model identity", "P0 and P1 are residual probabilistic GRUs over engineered states, not canonical GRU-D.", "descriptive_available", "development|evaluation", "model_family", "configs/closure_v2/analysis_plan.yaml", "models.labels", "model identity", "residual probabilistic GRU", "2 model families", "Masks and learned temporal decay required for canonical GRU-D were not implemented.", "residual probabilistic GRU", "canonical GRU-D"),
        _claim("C14_global_verdict", "V", "Conclusion", "V2 resolves temporal non-estimability but supplies a strong negative result for adaptive P1 on fresh-primary rather than superiority evidence.", "confirmatory_available", "fresh_primary", "observation_weighted", "reports/closure_v2/08_synthesis/THESIS_TABLES/T14_hypothesis_adjudication.csv", "H1-H5b", "global adjudication", "estimable_negative_result", "registered fresh-primary contrasts", "Engineering reproducibility remains distinct from predictive superiority.", "estimable negative result on the internal fresh-primary surface", "universal failure; external invalidity"),
        _claim("C15_summary_boundary", "Summary", "Summary", "The summary may state model availability, exact denominators and the fresh-primary negative result.", "descriptive_available", "all", "separate", "reports/closure_v2/08_synthesis/FINAL_CLOSURE_MATRIX.csv", "all rows", "authorized synthesis", "bounded V1/V2 result", "all registered evidence rows", "Cohorts and estimands must remain separate.", "internal, denominator-qualified negative result", "external validation; universal winner"),
        _claim("C16_abstract_boundary", "Abstract", "Abstract", "The abstract may report that V2 made P0/P1 estimable but did not support adaptive P1 superiority.", "descriptive_available", "fresh_primary", "observation_weighted", "reports/closure_v2/08_synthesis/FINAL_CLOSURE_MATRIX.csv", "evidence_block=inference", "authorized abstract boundary", "estimable but not superior", "fresh shared-success denominators", "No causal planning or field robustness language.", "P1 became estimable but was not superior", "causal management benefit; field guarantee"),
        _claim("C17_conclusion_boundary", "Conclusion", "Conclusion", "The conclusion may claim reproducibility and refutable negative evidence, not scientific efficacy certification.", "descriptive_available", "all", "separate", "reports/closure_v2/08_synthesis/THESIS_TABLES/T13_software_evidence.csv", "all rows", "reproducibility boundary", "reproducible negative evidence", "9 terminal software artifacts", "Certification and reproducibility do not establish efficacy.", "reproducible methodological contribution with bounded negative evidence", "certified scientific efficacy"),
    ]
    frame = pd.DataFrame(rows)
    required = ["claim_id", "chapter", "section", "claim_text", "claim_status", "cohort", "estimand", "artifact_path", "row_filter", "metric", "value", "denominator", "authority_commit", "limitation", "allowed_wording", "forbidden_wording"]
    if list(frame.columns) != required or frame[required].isna().any().any() or frame["claim_id"].duplicated().any():
        raise SynthesisError("Claim matrix contract drifted")
    return frame


def build_final_matrix(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    inference_records = cast(
        list[dict[str, Any]],
        pd.concat([tables["T06"], tables["T07"]], ignore_index=True).to_dict(orient="records"),
    )
    for row in inference_records:
        rows.append({
            "evidence_id": f"INF:{row['evaluation_cohort']}:{row['estimand']}:{row['comparison_id']}:h{row['horizon_months']}:{row['metric']}",
            "evidence_block": "inference", "hypothesis_id": "H2" if row["comparison_id"] == "P1_vs_B2" else "H1",
            "cohort": row["evaluation_cohort"], "estimand": row["estimand"],
            "comparison_or_scenario": row["comparison_id"], "horizon_months": row["horizon_months"],
            "metric": row["metric"], "estimate": row["estimate"], "ci95_lower": row["ci95_lower"],
            "ci95_upper": row["ci95_upper"], "denominator": row["shared_success_rows"],
            "availability_state": row["result_state"], "adjudication": row["adjudication"],
            "artifact_path": "reports/closure_v2/05_inference/pairwise_effects.csv",
            "limitation": "Cohort and estimand specific; no universal ranking.", "authority_commit": AUTHORITY_COMMIT,
        })
    degradation_records = cast(list[dict[str, Any]], tables["T10"].to_dict(orient="records"))
    for row in degradation_records:
        rows.append({
            "evidence_id": f"DEG:{row['evaluation_cohort']}:{row['estimand']}:{row['model_id']}:h{row['horizon_months']}:{row['degradation_family']}:{row['metric']}",
            "evidence_block": "degradation", "hypothesis_id": "H3|H4", "cohort": row["evaluation_cohort"],
            "estimand": row["estimand"], "comparison_or_scenario": f"{row['model_id']}:{row['degradation_family']}",
            "horizon_months": row["horizon_months"], "metric": f"aupd_{row['metric']}", "estimate": row["aupd"],
            "ci95_lower": np.nan, "ci95_upper": np.nan, "denominator": row["registered_seed_slots"],
            "availability_state": row["status"], "adjudication": "descriptive_only",
            "artifact_path": "reports/closure_v2/06_degradation/aupd.csv",
            "limitation": "Deterministic simulated missingness, not field robustness.", "authority_commit": AUTHORITY_COMMIT,
        })
    planning_records = cast(list[dict[str, Any]], tables["T11"].to_dict(orient="records"))
    for row in planning_records:
        rows.append({
            "evidence_id": f"PLAN:{row['evaluation_cohort']}:{row['scenario_id']}", "evidence_block": "planning",
            "hypothesis_id": "H5a", "cohort": row["evaluation_cohort"], "estimand": row["estimand"],
            "comparison_or_scenario": row["scenario_id"], "horizon_months": "1|2|3", "metric": "delta_objective_vs_no_action",
            "estimate": row["estimate"], "ci95_lower": row["ci95_lower"], "ci95_upper": row["ci95_upper"],
            "denominator": row["shared_success_row_count"], "availability_state": row["result_state"],
            "adjudication": "positive" if bool(row["reject_holm_0_05"]) else "no_positive_evidence",
            "artifact_path": "reports/closure_v2/07_planning/planning_bootstrap.csv",
            "limitation": "Raw-proxy simulation; no causality, official recommendation, or universal optimum.", "authority_commit": AUTHORITY_COMMIT,
        })
    frame = pd.DataFrame(rows).sort_values("evidence_id", kind="stable").reset_index(drop=True)
    if frame["evidence_id"].duplicated().any() or len(frame) != 162:
        raise SynthesisError(f"Final closure evidence universe drifted: {len(frame)}")
    return frame


def _svg_bars(title: str, labels: Sequence[str], values: Sequence[float], note: str) -> bytes:
    if len(labels) != len(values) or not labels:
        raise SynthesisError("SVG bar inputs are malformed")
    width, left, row_h = 1000, 285, 34
    height = 105 + row_h * len(labels)
    finite = [float(value) for value in values if np.isfinite(value)]
    bound = max(max((abs(value) for value in finite), default=1.0), 1e-12)
    scale = 310.0 / bound
    baseline = 640
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="30" y="32" font-family="sans-serif" font-size="20" font-weight="bold">{html.escape(title)}</text>',
        f'<text x="30" y="54" font-family="sans-serif" font-size="12" fill="#444">{html.escape(note)}</text>',
        f'<line x1="{baseline}" y1="68" x2="{baseline}" y2="{height - 20}" stroke="#555" stroke-width="1"/>',
    ]
    for index, (label, raw) in enumerate(zip(labels, values, strict=True)):
        y = 82 + index * row_h
        value = float(raw)
        bar = value * scale if np.isfinite(value) else 0.0
        x = baseline if bar >= 0 else baseline + bar
        color = "#2a6fbb" if bar >= 0 else "#c44e52"
        lines.extend([
            f'<text x="{left}" y="{y + 14}" text-anchor="end" font-family="sans-serif" font-size="12">{html.escape(str(label))}</text>',
            f'<rect x="{x:.2f}" y="{y}" width="{abs(bar):.2f}" height="18" fill="{color}" opacity="0.85"/>',
            f'<text x="{baseline + bar + (6 if bar >= 0 else -6):.2f}" y="{y + 14}" text-anchor="{"start" if bar >= 0 else "end"}" font-family="monospace" font-size="11">{value:.4g}</text>',
        ])
    lines.append("</svg>\n")
    return "\n".join(lines).encode("utf-8")


def _svg_lines(title: str, series: Mapping[str, Sequence[float]], note: str) -> bytes:
    width, height = 1000, 520
    all_values = [float(value) for values in series.values() for value in values if np.isfinite(value)]
    if not all_values or not series:
        raise SynthesisError("SVG line inputs are empty")
    lower, upper = min(all_values), max(all_values)
    span = max(upper - lower, 1e-12)
    max_len = max(len(values) for values in series.values())
    colors = ("#2a6fbb", "#dd8452", "#55a868", "#8172b3")
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="35" y="32" font-family="sans-serif" font-size="20" font-weight="bold">{html.escape(title)}</text>',
        f'<text x="35" y="54" font-family="sans-serif" font-size="12" fill="#444">{html.escape(note)}</text>',
        '<line x1="80" y1="450" x2="950" y2="450" stroke="#555"/><line x1="80" y1="80" x2="80" y2="450" stroke="#555"/>',
    ]
    for index, (label, values) in enumerate(series.items()):
        points = []
        for offset, value in enumerate(values):
            x = 80 + 870 * offset / max(max_len - 1, 1)
            y = 450 - 370 * (float(value) - lower) / span
            points.append(f"{x:.2f},{y:.2f}")
        color = colors[index % len(colors)]
        lines.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{760 + (index % 2) * 100}" y="{25 + (index // 2) * 18}" font-family="sans-serif" font-size="11" fill="{color}">{html.escape(label)}</text>')
    lines.append(f'<text x="80" y="482" font-family="sans-serif" font-size="11">1</text><text x="930" y="482" font-family="sans-serif" font-size="11">{max_len}</text>')
    lines.append("</svg>\n")
    return "\n".join(lines).encode("utf-8")


def build_figures(root: Path, tables: Mapping[str, pd.DataFrame]) -> dict[str, bytes]:
    t02 = tables["T02"].groupby("model_id", sort=True).first().reset_index()
    t03 = tables["T03"].groupby("model_id", sort=True).agg(max_abs_smd=("max_abs_smd", "max")).reset_index()
    curves: dict[str, list[np.ndarray]] = {"P0": [], "P1": []}
    for model in ("P0", "P1"):
        for seed in SEEDS:
            frame = _csv(root, f"reports/closure_v2/02_models/{model}/seed_{seed}/training_curve.csv")
            primary = frame.loc[frame["profile"].eq("v2_primary"), "probabilistic_validation_loss"].to_numpy(dtype=float)
            curves[model].append(primary)
    mean_curves = {
        model: pd.concat(
            [pd.Series(values_for_seed) for values_for_seed in values], axis=1,
        ).mean(axis=1).tolist()
        for model, values in curves.items()
    }
    benchmark = tables["T04"].loc[
        tables["T04"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T04"]["horizon_months"].eq(1) & tables["T04"]["metric"].eq("brier")
    ].sort_values("model_id")
    effects = tables["T06"].loc[
        tables["T06"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T06"]["estimand"].eq("observation_weighted")
    ]
    uncertainty = tables["T09"].loc[
        tables["T09"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T09"]["coverage_nominal"].eq(0.9) & tables["T09"]["horizon_months"].eq(1)
    ].sort_values("model_id")
    degradation = tables["T10"].loc[
        tables["T10"]["evaluation_cohort"].eq("fresh_primary")
        & tables["T10"]["estimand"].eq("observation_weighted")
        & tables["T10"]["horizon_months"].eq(1) & tables["T10"]["metric"].eq("brier")
    ].sort_values(["model_id", "degradation_family"])
    planning = tables["T11"].loc[tables["T11"]["evaluation_cohort"].eq("fresh_primary")]
    verdict_score = {
        "not_supported_on_fresh_primary": -1.0, "estimable_negative_result": -1.0,
        "partial_descriptive_support": 0.25, "estimable_descriptive_contrast": 0.25,
        "not_supported": -1.0, "not_estimable_registered_scope": 0.0,
    }
    hypotheses = tables["T14"]
    return {
        "F01": _svg_bars("F01 Fit eligibility", t02["model_id"].tolist(), t02["fit_eligibility_fraction"].tolist(), "Shared complete-case fit fraction; denominator retained in T02."),
        "F02": _svg_bars("F02 Eligibility bias", t03["model_id"].tolist(), t03["max_abs_smd"].tolist(), "Maximum absolute standardized mean difference; descriptive only."),
        "F03": _svg_lines("F03 Training curves", mean_curves, "Mean development validation loss across five registered algorithmic seeds."),
        "F04": _svg_bars("F04 Fresh-primary Brier h1", benchmark["model_id"].tolist(), benchmark["estimate"].tolist(), "Observation-weighted family estimates; lower is better; availability in T04."),
        "F05": _svg_bars("F05 P1 versus B2 paired effects", [f"h{r.horizon_months} {r.metric}" for r in effects.itertuples()], effects["estimate"].tolist(), "Fresh-primary observation-weighted paired differences; direction defined in T06."),
        "F06": _svg_bars("F06 Fresh-primary interval coverage", uncertainty["model_id"].tolist(), uncertainty["picp"].tolist(), "Nominal 0.90, h1; non-applicable values are labelled nan and defined in T09."),
        "F07": _svg_bars("F07 Degradation AUPD", [f"{r.model_id}:{r.degradation_family}" for r in degradation.itertuples()], degradation["aupd"].tolist(), "Fresh-primary observation-weighted Brier retention, h1; simulated missingness."),
        "F08": _svg_bars("F08 Planning objective effects", planning["scenario_id"].tolist(), planning["estimate"].tolist(), "Fresh-primary action minus no_action objective; clustered IC/Holm in T11."),
        "F09": _svg_bars("F09 V1-V2 provenance", ["V1 frozen", "V2 legacy", "V2 fresh", "software"], [1.0, 2.0, 3.0, 4.0], "Ordinal provenance layers only; bar length is not scientific magnitude."),
        "F10": _svg_bars("F10 Hypothesis verdicts", hypotheses["hypothesis_id"].tolist(), [verdict_score[str(value)] for value in hypotheses["v2_verdict"]], "-1 not supported/negative; 0 not estimable; +0.25 descriptive evidence."),
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.10g", na_rep="").encode("utf-8")


def _report_bytes(tables: Mapping[str, pd.DataFrame], claims: pd.DataFrame, final: pd.DataFrame) -> bytes:
    fresh_b2 = tables["T06"].loc[(tables["T06"]["evaluation_cohort"].eq("fresh_primary")) & (tables["T06"]["estimand"].eq("observation_weighted"))]
    fresh_p0 = tables["T07"].loc[(tables["T07"]["evaluation_cohort"].eq("fresh_primary")) & (tables["T07"]["estimand"].eq("observation_weighted"))]
    planning = tables["T11"].loc[tables["T11"]["evaluation_cohort"].eq("fresh_primary")]
    lines = [
        "# FINAL CLOSURE REPORT — Closure V2", "",
        "## 1. Authority and evidence boundary", "",
        f"Closure V2 synthesis authority is `{AUTHORITY_COMMIT}`. Closure V1 remains immutable at its published authorities; V2 is additive and does not retroactively change V1 model availability or claims. This synthesis consumed only {len(INPUTS)} allowlisted structured Git inputs. It did not read raw targets, Parquet, or `private/FULL.md`, and did not refit, rescore, recalibrate, or pool cohorts/estimands.", "",
        "## 2. Eligibility and model availability", "",
        "All five P0 and five P1 slots were trained and calibrated without replacement on the same 8,925 complete-case shared-fit rows from 9,413 fit-intent rows. The 505 incomplete origins remain visible in the ledger. Seeds are algorithmic slots, not ecological replicates.", "",
        "## 3. Evaluation surfaces", "",
        "`fresh_primary` contains 2,286 origins from 137 WQP monitoring locations unused by V1 and is the maximum internal evidence layer. `legacy_posthoc` contains 4,488 origins from the 88 previously opened V1 locations and is retrospective complementary evidence. They are never pooled.", "",
        "## 4. Primary inferential result", "",
        f"On fresh-primary observation-weighted common rows, P1 versus B2 was `{fresh_b2['adjudication'].value_counts().to_dict()}` across Brier and PR-AUC at h1-h3. P1 versus P0 was `{fresh_p0['adjudication'].value_counts().to_dict()}`. Thus V2 resolves the V1 structural non-estimability, but the registered fresh-primary evidence does not support superiority of the adaptive P1 branch. The favorable P1-P0 result in legacy-posthoc remains retrospective and cannot overturn the fresh-primary result.", "",
        "## 5. Uncertainty, degradation and planning", "",
        "Uncertainty diagnostics are reported by model, cohort and horizon without a global calibration claim. Degradation uses identical deterministic masks and frozen models; it supports only robustness statements under simulated missingness. No universal M0-P1 crossover was found.", "",
        f"All {len(planning)} fresh-primary planning actions had negative objective estimates after the registered cost, support and uncertainty terms; Holm rejected none. This is valid negative model-behavior evidence, not evidence that interventions fail in the field, and not an official recommendation.", "",
        "## 6. H1-H5b adjudication", "",
        tables["T14"].to_markdown(index=False), "",
        "## 7. Global verdict", "",
        "Closure V2 provides a completed, reproducible and refutable temporal experiment. It converts the unavailable V1 P0/P1 question into an estimable negative result: on the internal fresh-primary surface, the adaptive P1 branch did not outperform the registered comparators and was inferior on the primary P1-B2 contrasts. This does not establish external invalidity, universal model inferiority, field causality, or lack of management value.", "",
        "## 8. Thesis package", "",
        f"The package contains {len(final)} final evidence rows, {len(claims)} claim mappings, 14 deterministic tables and 10 deterministic SVG figures. Every claim provides cohort, estimand, denominator, artifact, authority and wording boundaries. `MANUSCRIPT_CHANGE_MAP.md` is a handoff only; this phase does not modify LaTeX.", "",
    ]
    return "\n".join(lines).encode("utf-8")


def _change_map_bytes() -> bytes:
    sections = [
        ("Resumen", "C04,C05,C06,C14,C15", "T01,T06,T07,T14", "F05,F10", "10/10 model slots; 966|933|885 shared fresh rows", "V2 made P0/P1 estimable but did not support adaptive P1 superiority.", "external validation; universal superiority; causal planning"),
        ("Abstract", "C01,C05,C06,C16", "T04,T06,T07", "F04,F05", "2,286 origins; 137 locations; shared rows by horizon", "Internal evaluation on unused WQP monitoring locations produced an estimable negative result.", "unseen waterbodies; prospective external validation"),
        ("Capítulo III", "C01,C02,C03,C04", "T01,T02,T03,T12", "F01,F02,F09", "9,732 intent; 9,413 fit-intent; 8,925 shared fit", "Document complete-case shared fit, retained attrition, five slots and separate evidence layers.", "masked-loss primary analysis; seed ecological replication"),
        ("Capítulo IV", "C05-C11", "T04-T11,T14", "F03-F08,F10", "row-specific attempted/shared-success/cluster denominators", "Report fresh-primary first, legacy-posthoc separately, including negative and non-estimable results.", "select only favorable results; pool cohorts or estimands"),
        ("Capítulo V", "C12-C14,C17", "T12-T14", "F09,F10", "162 final evidence rows", "Discuss the strong bounded negative result and distinguish reproducibility from efficacy.", "retroactive V1 correction; universal failure"),
        ("Anexos", "all claims", "T01-T14", "F01-F10", "published denominator per row", "Include hashes, manifests, captions, provenance and wording boundaries.", "local paths; secrets; scientific claims from software checks"),
    ]
    lines = ["# Closure V2 manuscript change map", "", "This map is a handoff. It does not authorize editing the LaTeX project before editorial approval of the synthesis bundle.", ""]
    for section, claims, tables, figures, denominator, allowed, forbidden in sections:
        lines.extend([
            f"## {section}", "", f"- Claims: `{claims}`", f"- Tables: `{tables}`", f"- Figures: `{figures}`",
            f"- Denominator: {denominator}", f"- Allowed wording: {allowed}", f"- Forbidden wording: {forbidden}", "",
        ])
    return "\n".join(lines).encode("utf-8")


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, payload in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise SynthesisError(f"Refusing to overwrite synthesis output: {relative}")
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
            temp = Path(temp_name)
            temporaries.append(temp)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temp, destination)
            inode = destination.stat().st_ino
            created.append((destination, inode))
            temp.unlink()
            temporaries.remove(temp)
    except BaseException:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        for temp in temporaries:
            if temp.is_file() and not temp.is_symlink():
                temp.unlink()
        raise


def execute(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_authority(root)
    tables = build_tables(root)
    claims = build_claims(tables)
    final = build_final_matrix(tables)
    figures = build_figures(root, tables)
    if set(figures) != set(FIGURE_NAMES):
        raise SynthesisError("The 10-figure synthesis universe is incomplete")
    contents: list[tuple[Path, bytes]] = [
        (FINAL_MATRIX, _csv_bytes(final)), (CLAIM_MATRIX, _csv_bytes(claims)),
        (REPORT, _report_bytes(tables, claims, final)), (CHANGE_MAP, _change_map_bytes()),
    ]
    contents.extend((TABLE_ROOT / TABLE_NAMES[key], _csv_bytes(tables[key])) for key in TABLE_NAMES)
    contents.extend((FIGURE_ROOT / FIGURE_NAMES[key], figures[key]) for key in FIGURE_NAMES)
    manifest = {
        "schema_version": "closure_v2_synthesis_manifest_v1", "experiment_id": "closure_v2",
        "phase": "P17", "status": "completed", "authority_commit": AUTHORITY_COMMIT,
        "script": _record(root, SCRIPT_PATH, "deterministic_structured_synthesis_builder"),
        "inputs": [_record(root, path, "allowlisted_structured_input") for path in INPUTS],
        "outputs": [
            _payload_record(path, payload, "thesis_synthesis_output")
            for path, payload in contents
        ],
        "output_count": len(contents) + 1, "table_count": 14, "figure_count": 10,
        "final_closure_rows": len(final), "claim_rows": len(claims),
        "claim_columns": list(claims.columns), "fresh_primary_present": True,
        "fresh_primary_origins": 2286, "legacy_posthoc_origins": 4488,
        "v1_immutable": True, "v2_additive": True, "cohorts_pooled": False,
        "estimands_pooled": False, "raw_targets_read": False, "parquet_read": False,
        "private_full_read": False, "models_recomputed": False, "metrics_recomputed": False,
        "refit_performed": False, "recalibration_performed": False,
        "latex_modified": False, "field_causality_claimed": False,
        "external_validation_claimed": False, "official_recommendation_claimed": False,
        "universal_superiority_claimed": False, "negative_results_retained": True,
        "manifest_written_last": True,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    _exclusive_bundle([*contents, (MANIFEST, manifest_bytes)], root)
    return {
        **authority, "status": "closure_v2_synthesis_completed",
        "final_closure_rows": len(final), "claim_rows": len(claims),
        "table_count": len(tables), "figure_count": len(figures),
        "manifest_sha256": _sha256(root / MANIFEST), "manifest_written_last": True,
    }


def preflight(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return validate_authority(root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute() if args.execute else preflight()
    print(_canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
