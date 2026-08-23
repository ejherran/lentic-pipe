#!/usr/bin/env python
"""Run Closure V2 P14 clustered inference on the published P13 family rows."""

from __future__ import annotations

import argparse
import hashlib
import io
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from sklearn.metrics import average_precision_score

from src.experiments.closure_contract import ClosureContractError, load_json_mapping, load_yaml_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.hashing import canonical_json_bytes, md5_file, sha256_file


SCRIPT_PATH = Path("src/experiments/closure_v2/run_inference.py")
ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
MODEL_LOCK = Path("reports/closure_v2/00_protocol/model_lock.json")
EVALUATION_MANIFEST = Path("reports/closure_v2/04_evaluation/evaluation_manifest.json")
PREDICTIONS = Path("data/closure_v2/predictions_long.parquet")
PREDICTIONS_POINTER = Path("data/closure_v2/predictions_long.parquet.dvc")
OUTPUT_ROOT = Path("reports/closure_v2/05_inference")
SITE_LOSSES = OUTPUT_ROOT / "site_level_losses.csv"
PAIRWISE_EFFECTS = OUTPUT_ROOT / "pairwise_effects.csv"
MULTIPLICITY = OUTPUT_ROOT / "multiplicity_report.csv"
BOOTSTRAP_SUMMARY = OUTPUT_ROOT / "bootstrap_summary.csv"
BOOTSTRAP_DISTRIBUTIONS = OUTPUT_ROOT / "bootstrap_distributions.parquet"
BOOTSTRAP_POINTER = OUTPUT_ROOT / "bootstrap_distributions.parquet.dvc"
REPORT = OUTPUT_ROOT / "STATISTICAL_INFERENCE_REPORT.md"
INFERENCE_MANIFEST = OUTPUT_ROOT / "inference_manifest.json"
MATERIALIZED_OUTPUTS = (
    SITE_LOSSES, PAIRWISE_EFFECTS, MULTIPLICITY, BOOTSTRAP_SUMMARY, BOOTSTRAP_DISTRIBUTIONS,
)
ALL_OUTPUTS = (*MATERIALIZED_OUTPUTS, BOOTSTRAP_POINTER, REPORT, INFERENCE_MANIFEST)
COMPARISONS = (
    ("P1_vs_B2", "P1", "B2", "primary"),
    ("P1_vs_P0", "P1", "P0", "primary"),
)
METRICS = ("brier", "pr_auc")
ESTIMANDS = ("observation_weighted", "site_weighted")
COHORTS = ("legacy_posthoc", "fresh_primary")
HORIZONS = (1, 2, 3)
BOOTSTRAP_REPLICATES = 2000
CONFIDENCE_LEVEL = 0.95
MINIMUM_PR_VALID_FRACTION = 0.95
RNG_SEED = 1729
P13_COMMIT = "047c614944e66b2ba7e5229cc289ce317ba3602a"
FAMILIES = {
    "A": tuple(f"P1_vs_B2_brier_h{horizon}" for horizon in HORIZONS),
    "B": tuple(f"P1_vs_P0_brier_h{horizon}" for horizon in HORIZONS),
    "C": tuple(
        f"{comparison}_pr_auc_h{horizon}"
        for comparison in ("P1_vs_B2", "P1_vs_P0")
        for horizon in HORIZONS
    ),
}
PREEXECUTION_IMPLEMENTATION_PATHS = {
    SCRIPT_PATH.as_posix(),
    "tests/closure_v2/test_run_inference.py",
}


class InferenceError(ClosureContractError):
    """Raised when P14 violates a sealed inference boundary."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise InferenceError(f"Required regular file is absent: {relative}")
    return path


def _verify_file_record(root: Path, record: Mapping[str, Any]) -> None:
    relative = Path(str(record.get("path", "")))
    path = _require_regular(root, relative)
    if path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
        raise InferenceError(f"P13 artifact binding drifted: {relative}")


def validate_p13(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", "origin/closure-v2", root=root)
    if head != P13_COMMIT or remote != head:
        raise InferenceError("P14 requires the exact published P13 commit")
    changed = {
        value
        for command in (("diff", "--name-only"), ("diff", "--cached", "--name-only"), ("ls-files", "--others", "--exclude-standard"))
        for value in _git(*command, root=root).splitlines()
        if value
    }
    if not changed.issubset(PREEXECUTION_IMPLEMENTATION_PATHS):
        raise InferenceError(f"Unexpected P14 pre-execution changes: {sorted(changed - PREEXECUTION_IMPLEMENTATION_PATHS)}")
    plan = load_yaml_mapping(_require_regular(root, ANALYSIS_PLAN))
    inference = plan.get("inference")
    multiplicity = plan.get("multiplicity")
    if not isinstance(inference, Mapping) or not isinstance(multiplicity, Mapping):
        raise InferenceError("Analysis-plan inference contract is malformed")
    if (
        inference.get("unit") != "source_id_plus_site_id"
        or inference.get("paired_shared_success") is not True
        or inference.get("bootstrap_replicates") != BOOTSTRAP_REPLICATES
        or inference.get("confidence_level") != CONFIDENCE_LEVEL
        or inference.get("pr_auc_minimum_valid_replicate_fraction") != MINIMUM_PR_VALID_FRACTION
        or inference.get("seed_pseudoreplication") != "forbidden"
        or multiplicity.get("method") != "holm"
        or multiplicity.get("reduce_family_for_unavailable_contrast") is not False
    ):
        raise InferenceError("Analysis-plan inference decision drifted")
    configured_families = multiplicity.get("families")
    if not isinstance(configured_families, Mapping) or any(
        configured_families.get(name) != list(hypotheses) for name, hypotheses in FAMILIES.items()
    ):
        raise InferenceError("Registered Holm families A-C drifted")
    manifest = load_json_mapping(_require_regular(root, EVALUATION_MANIFEST))
    required = {
        "status": "completed", "phase": "P13", "prediction_rows": 650_304,
        "family_prediction": "mean_probability_over_available_registered_seeds",
        "seed_pseudoreplication": False, "inference_performed": False,
        "refit_performed": False, "recalibration_performed": False,
        "legacy_and_fresh_pooled": False, "manifest_written_last": True,
        "failed_prediction_values_nulled": True,
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise InferenceError("P13 evaluation manifest drifted")
    for record in cast(Sequence[Mapping[str, Any]], manifest.get("inputs", [])):
        _verify_file_record(root, record)
    for record in cast(Sequence[Mapping[str, Any]], manifest.get("outputs", [])):
        _verify_file_record(root, record)
    data = manifest.get("data_artifact")
    if not isinstance(data, Mapping):
        raise InferenceError("P13 prediction binding is absent")
    _verify_file_record(root, data)
    pointer = yaml.safe_load(_require_regular(root, PREDICTIONS_POINTER).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise InferenceError("P13 prediction pointer is malformed")
    if (
        outs[0].get("path") != PREDICTIONS.name
        or outs[0].get("md5") != data.get("dvc_md5")
        or outs[0].get("size") != data.get("dvc_size")
        or md5_file(root / PREDICTIONS) != data.get("dvc_md5")
    ):
        raise InferenceError("P13 prediction pointer drifted")
    return {
        "status": "p13_effective", "head": head,
        "evaluation_manifest_sha256": sha256_file(root / EVALUATION_MANIFEST),
        "predictions_sha256": sha256_file(root / PREDICTIONS),
        "prediction_rows": 650_304,
    }


def _load_family_predictions(root: Path) -> pd.DataFrame:
    columns = [
        "evaluation_cohort", "model_id", "base_seed", "aggregation_level",
        "origin_id", "source_id", "site_id", "origin_year_month", "target_year_month",
        "horizon_months", "prediction_successful", "target_available", "metric_evaluable",
        "shared_success", "bloom_probability", "outcome_bloom_30",
    ]
    frame = pq.read_table(_require_regular(root, PREDICTIONS), columns=columns).to_pandas()
    family = frame.loc[
        frame["aggregation_level"].astype(str).eq("family")
        & frame["base_seed"].eq(-1)
        & frame["model_id"].isin(["P0", "P1", "B2"])
    ].copy()
    expected = 3 * 3 * (4488 + 2286)
    if len(family) != expected or family.duplicated([
        "evaluation_cohort", "model_id", "source_id", "site_id",
        "origin_year_month", "horizon_months",
    ]).any():
        raise InferenceError("P13 family prediction universe drifted")
    if not family.loc[~family["prediction_successful"], "bloom_probability"].isna().all():
        raise InferenceError("Failed P13 family rows carry prediction values")
    return family


def _paired_surface(
    family: pd.DataFrame,
    comparison_id: str,
    challenger: str,
    reference: str,
) -> pd.DataFrame:
    keys = [
        "evaluation_cohort", "origin_id", "source_id", "site_id",
        "origin_year_month", "target_year_month", "horizon_months",
    ]
    fields = [*keys, "shared_success", "metric_evaluable", "bloom_probability", "outcome_bloom_30"]
    left = family.loc[family["model_id"].eq(challenger), fields]
    right = family.loc[family["model_id"].eq(reference), fields]
    paired = left.merge(right, on=keys, how="outer", validate="one_to_one", suffixes=("_challenger", "_reference"), indicator=True)
    if not paired["_merge"].eq("both").all():
        raise InferenceError(f"Pairwise intent keys differ: {comparison_id}")
    boolean_pairs = (("shared_success_challenger", "shared_success_reference"), ("outcome_bloom_30_challenger", "outcome_bloom_30_reference"))
    if any(not paired[a].equals(paired[b]) for a, b in boolean_pairs):
        raise InferenceError(f"Pairwise status/outcome binding differs: {comparison_id}")
    paired = paired.loc[paired["shared_success_challenger"].astype(bool)].copy()
    if (
        paired.empty
        or not paired[["metric_evaluable_challenger", "metric_evaluable_reference"]].all(axis=1).all()
        or paired[["bloom_probability_challenger", "bloom_probability_reference"]].isna().any().any()
    ):
        raise InferenceError(f"Shared-success surface is unavailable: {comparison_id}")
    paired["comparison_id"] = comparison_id
    paired["challenger"] = challenger
    paired["reference"] = reference
    paired["y_true"] = paired["outcome_bloom_30_challenger"].astype(int)
    paired["cluster_id"] = paired["source_id"].astype(str) + "::" + paired["site_id"].astype(str)
    return paired.drop(columns=["_merge"])


def _metric_value(y: np.ndarray, p: np.ndarray, weights: np.ndarray, metric: str) -> float:
    if metric == "brier":
        return float(np.average((p - y) ** 2, weights=weights))
    if metric == "pr_auc":
        if len(np.unique(y[weights > 0])) < 2:
            return math.nan
        return float(average_precision_score(y, p, sample_weight=weights))
    raise InferenceError(f"Unknown inference metric: {metric}")


def _point_weights(frame: pd.DataFrame, estimand: str) -> np.ndarray:
    if estimand == "observation_weighted":
        return np.ones(len(frame), dtype=np.float64)
    counts = frame.groupby("cluster_id", sort=False)["origin_id"].transform("size")
    return 1.0 / counts.to_numpy(dtype=np.float64)


def _site_rows(surface: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cluster_id, group in surface.groupby("cluster_id", sort=True):
        y = group["y_true"].to_numpy(dtype=int)
        challenger = group["bloom_probability_challenger"].to_numpy(dtype=np.float64)
        reference = group["bloom_probability_reference"].to_numpy(dtype=np.float64)
        weights = np.ones(len(group), dtype=np.float64)
        a = _metric_value(y, challenger, weights, metric)
        b = _metric_value(y, reference, weights, metric)
        valid = math.isfinite(a) and math.isfinite(b)
        delta = a - b if valid else math.nan
        rows.append({
            "evaluation_cohort": str(group["evaluation_cohort"].iloc[0]),
            "comparison_id": str(group["comparison_id"].iloc[0]),
            "challenger": str(group["challenger"].iloc[0]),
            "reference": str(group["reference"].iloc[0]),
            "horizon_months": int(group["horizon_months"].iloc[0]),
            "metric": metric, "source_id": str(group["source_id"].iloc[0]),
            "site_id": str(group["site_id"].iloc[0]), "cluster_id": cluster_id,
            "shared_success_rows": len(group),
            "positive_rows": int(y.sum()), "negative_rows": int((1 - y).sum()),
            "challenger_metric": a, "reference_metric": b, "delta_challenger_minus_reference": delta,
            "challenger_better": bool(delta < 0.0) if metric == "brier" and valid else bool(delta > 0.0) if valid else False,
            "status": "estimated" if valid else "not_estimable_single_class",
        })
    return pd.DataFrame(rows)


def _substream_seed(cohort: str, estimand: str, horizon: int) -> int:
    digest = hashlib.sha256(f"{RNG_SEED}\0{cohort}\0{estimand}\0{horizon}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


def _bootstrap_effect(
    surface: pd.DataFrame,
    *,
    metric: str,
    estimand: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    ordered = surface.sort_values(["cluster_id", "origin_year_month"], kind="stable").reset_index(drop=True)
    clusters = sorted(ordered["cluster_id"].astype(str).unique())
    cluster_codes = pd.Categorical(ordered["cluster_id"].astype(str), categories=clusters).codes
    cluster_rows = np.bincount(cluster_codes, minlength=len(clusters)).astype(np.float64)
    y = ordered["y_true"].to_numpy(dtype=int)
    challenger = ordered["bloom_probability_challenger"].to_numpy(dtype=np.float64)
    reference = ordered["bloom_probability_reference"].to_numpy(dtype=np.float64)
    point_weights = _point_weights(ordered, estimand)
    challenger_point = _metric_value(y, challenger, point_weights, metric)
    reference_point = _metric_value(y, reference, point_weights, metric)
    estimate = challenger_point - reference_point
    rng = np.random.default_rng(_substream_seed(
        str(ordered["evaluation_cohort"].iloc[0]), estimand, int(ordered["horizon_months"].iloc[0])
    ))
    records: list[dict[str, Any]] = []
    values = np.full(BOOTSTRAP_REPLICATES, np.nan, dtype=np.float64)
    for replicate in range(BOOTSTRAP_REPLICATES):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        multiplicity = np.bincount(selected, minlength=len(clusters)).astype(np.float64)
        weights = multiplicity[cluster_codes]
        if estimand == "site_weighted":
            weights = weights / cluster_rows[cluster_codes]
        a = _metric_value(y, challenger, weights, metric)
        b = _metric_value(y, reference, weights, metric)
        valid = math.isfinite(a) and math.isfinite(b)
        if valid:
            values[replicate] = a - b
        records.append({
            "evaluation_cohort": str(ordered["evaluation_cohort"].iloc[0]),
            "estimand": estimand, "comparison_id": str(ordered["comparison_id"].iloc[0]),
            "challenger": str(ordered["challenger"].iloc[0]), "reference": str(ordered["reference"].iloc[0]),
            "horizon_months": int(ordered["horizon_months"].iloc[0]), "metric": metric,
            "replicate": replicate + 1, "cluster_draws": len(clusters),
            "unique_clusters_sampled": int((multiplicity > 0).sum()),
            "replicate_status": "estimated" if valid else "replicate_not_estimable_single_class",
            "delta_challenger_minus_reference": values[replicate],
        })
    valid_values = values[np.isfinite(values)]
    valid_fraction = len(valid_values) / BOOTSTRAP_REPLICATES
    interval_available = bool(
        len(valid_values) == BOOTSTRAP_REPLICATES
        if metric == "brier"
        else valid_fraction >= MINIMUM_PR_VALID_FRACTION
    )
    summary = {
        "estimate": estimate,
        "challenger_estimate": challenger_point,
        "reference_estimate": reference_point,
        "shared_success_rows": len(ordered),
        "shared_success_clusters": len(clusters),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "valid_replicates": len(valid_values),
        "invalid_replicates": BOOTSTRAP_REPLICATES - len(valid_values),
        "valid_replicate_fraction": valid_fraction,
        "ci95_lower": float(np.quantile(valid_values, 0.025)) if interval_available else math.nan,
        "ci95_upper": float(np.quantile(valid_values, 0.975)) if interval_available else math.nan,
        "interval_status": "available" if interval_available else "not_estimable_insufficient_valid_replicates",
    }
    return summary, pd.DataFrame(records)


def _adjudication(metric: str, estimate: float, lower: float, upper: float) -> str:
    if not all(math.isfinite(value) for value in (estimate, lower, upper)):
        return "not_estimable"
    if metric == "brier":
        if upper < 0.0:
            return "superior"
        if lower > 0.0:
            return "inferior"
        if estimate < 0.0:
            return "descriptively_favorable"
        return "inconclusive"
    if lower > 0.0:
        return "superior"
    if upper < 0.0:
        return "inferior"
    if estimate > 0.0:
        return "descriptively_favorable"
    return "inconclusive"


def _registered_hypothesis(cohort: str, estimand: str, comparison: str, metric: str, horizon: int) -> tuple[str, str] | tuple[None, None]:
    if cohort != "fresh_primary" or estimand != "observation_weighted":
        return None, None
    hypothesis = f"{comparison}_{metric}_h{horizon}"
    for family, members in FAMILIES.items():
        if hypothesis in members:
            return hypothesis, family
    return None, None


def build_inference_tables(family: pd.DataFrame) -> dict[str, pd.DataFrame]:
    site_tables: list[pd.DataFrame] = []
    effects: list[dict[str, Any]] = []
    distributions: list[pd.DataFrame] = []
    for comparison_id, challenger, reference, tier in COMPARISONS:
        paired = _paired_surface(family, comparison_id, challenger, reference)
        for cohort in COHORTS:
            for horizon in HORIZONS:
                surface = paired.loc[
                    paired["evaluation_cohort"].eq(cohort) & paired["horizon_months"].eq(horizon)
                ].copy()
                if surface.empty:
                    raise InferenceError(f"Registered pairwise surface is empty: {comparison_id}/{cohort}/h{horizon}")
                metric_site_tables = {metric: _site_rows(surface, metric) for metric in METRICS}
                site_tables.extend(metric_site_tables.values())
                for estimand in ESTIMANDS:
                    for metric in METRICS:
                        summary, distribution = _bootstrap_effect(surface, metric=metric, estimand=estimand)
                        distributions.append(distribution)
                        site = metric_site_tables[metric]
                        valid_site = site.loc[site["status"].eq("estimated")]
                        hypothesis, family_id = _registered_hypothesis(cohort, estimand, comparison_id, metric, horizon)
                        effect = {
                            "evaluation_cohort": cohort, "estimand": estimand,
                            "comparison_id": comparison_id, "comparison_tier": tier,
                            "challenger": challenger, "reference": reference,
                            "horizon_months": horizon, "metric": metric,
                            "direction": "lower_is_better" if metric == "brier" else "higher_is_better",
                            **summary,
                            "site_improvement_numerator": int(valid_site["challenger_better"].sum()),
                            "site_improvement_denominator": len(valid_site),
                            "proportion_sites_challenger_better": float(valid_site["challenger_better"].mean()) if len(valid_site) else math.nan,
                            "registered_hypothesis_id": hypothesis,
                            "holm_family": family_id,
                            "raw_p_value": math.nan,
                            "holm_p_value": math.nan,
                            "p_value_status": "not_computed_not_predeclared",
                            "holm_universe_retained": bool(hypothesis is not None),
                            "result_state": "posthoc_available" if cohort == "legacy_posthoc" else "confirmatory_available",
                            "adjudication": _adjudication(metric, summary["estimate"], summary["ci95_lower"], summary["ci95_upper"]),
                            "seed_pseudoreplication": False,
                        }
                        effects.append(effect)
    site_losses = pd.concat(site_tables, ignore_index=True).sort_values(
        ["evaluation_cohort", "comparison_id", "horizon_months", "metric", "cluster_id"], kind="stable"
    ).reset_index(drop=True)
    pairwise = pd.DataFrame(effects).sort_values(
        ["evaluation_cohort", "estimand", "comparison_id", "horizon_months", "metric"], kind="stable"
    ).reset_index(drop=True)
    bootstrap = pd.concat(distributions, ignore_index=True).sort_values(
        ["evaluation_cohort", "estimand", "comparison_id", "horizon_months", "metric", "replicate"], kind="stable"
    ).reset_index(drop=True)
    summary_columns = [
        "evaluation_cohort", "estimand", "comparison_id", "challenger", "reference",
        "horizon_months", "metric", "estimate", "shared_success_rows", "shared_success_clusters",
        "bootstrap_replicates", "valid_replicates", "invalid_replicates", "valid_replicate_fraction",
        "ci95_lower", "ci95_upper", "interval_status", "adjudication", "result_state",
    ]
    bootstrap_summary = pairwise[summary_columns].copy()
    multiplicity_rows = []
    registered = pairwise.loc[pairwise["registered_hypothesis_id"].notna()]
    for family_id, hypotheses in FAMILIES.items():
        for hypothesis in hypotheses:
            matched = registered.loc[registered["registered_hypothesis_id"].eq(hypothesis)]
            if len(matched) != 1:
                raise InferenceError(f"Registered Holm hypothesis coverage drifted: {hypothesis}")
            row = matched.iloc[0]
            multiplicity_rows.append({
                "hypothesis_id": hypothesis, "holm_family": family_id,
                "holm_universe_size": len(hypotheses), "holm_method": "holm",
                "evaluation_cohort": "fresh_primary", "estimand": "observation_weighted",
                "comparison_id": row["comparison_id"], "horizon_months": row["horizon_months"],
                "metric": row["metric"], "effect_estimate": row["estimate"],
                "ci95_lower": row["ci95_lower"], "ci95_upper": row["ci95_upper"],
                "raw_p_value": math.nan, "holm_p_value": math.nan,
                "multiplicity_status": "not_applied_bootstrap_p_value_not_predeclared",
                "holm_universe_retained": True, "holm_universe_reduced": False,
                "adjudication_from_ci": row["adjudication"],
            })
    multiplicity = pd.DataFrame(multiplicity_rows)
    if multiplicity.groupby("holm_family").size().to_dict() != {"A": 3, "B": 3, "C": 6}:
        raise InferenceError("Holm A-C universe was reduced")
    return {
        "site_level_losses": site_losses,
        "pairwise_effects": pairwise,
        "multiplicity_report": multiplicity,
        "bootstrap_summary": bootstrap_summary,
        "bootstrap_distributions": bootstrap,
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False), buffer,
        compression="zstd", use_dictionary=False, write_statistics=True,
        data_page_version="1.0",
    )
    return buffer.getvalue()


def _payloads(tables: Mapping[str, pd.DataFrame]) -> dict[Path, bytes]:
    return {
        SITE_LOSSES: _csv_bytes(tables["site_level_losses"]),
        PAIRWISE_EFFECTS: _csv_bytes(tables["pairwise_effects"]),
        MULTIPLICITY: _csv_bytes(tables["multiplicity_report"]),
        BOOTSTRAP_SUMMARY: _csv_bytes(tables["bootstrap_summary"]),
        BOOTSTRAP_DISTRIBUTIONS: _parquet_bytes(tables["bootstrap_distributions"]),
    }


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporaries: list[Path] = []
    try:
        for relative, payload in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise InferenceError(f"Refusing to overwrite P14 output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporaries.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
    except BaseException:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def preflight(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p13(root)
    family = _load_family_predictions(root)
    counts = {}
    for comparison_id, challenger, reference, _ in COMPARISONS:
        paired = _paired_surface(family, comparison_id, challenger, reference)
        grouped_counts: dict[str, dict[str, int]] = {}
        for raw_keys, part in paired.groupby(["evaluation_cohort", "horizon_months"], sort=True):
            cohort, horizon = cast(tuple[Any, Any], raw_keys)
            grouped_counts[f"{cohort}_h{horizon}"] = {
                "shared_success_rows": len(part), "clusters": int(part["cluster_id"].nunique())
            }
        counts[comparison_id] = grouped_counts
    return {
        **authority, "status": "ready_for_clustered_inference",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "cluster_unit": "source_id_plus_site_id", "comparisons": counts,
        "holm_universes": {key: len(value) for key, value in FAMILIES.items()},
        "bootstrap_p_value_predeclared": False,
        "outputs_absent": all(not (root / path).exists() and not (root / path).is_symlink() for path in ALL_OUTPUTS),
        "writes_performed": False,
    }


def execute(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_p13(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in ALL_OUTPUTS):
        raise InferenceError("P14 output namespace is not empty")
    guard = root / "tmp/closure_v2_inference.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise InferenceError("P14 inference guard already exists") from error
    try:
        family = _load_family_predictions(root)
        first = build_inference_tables(family)
        first_payloads = _payloads(first)
        second_payloads = _payloads(build_inference_tables(family.copy(deep=True)))
        if {key: hashlib.sha256(value).hexdigest() for key, value in first_payloads.items()} != {
            key: hashlib.sha256(value).hexdigest() for key, value in second_payloads.items()
        }:
            raise InferenceError("P14 reproducibility check failed")
        _exclusive_bundle([(path, first_payloads[path]) for path in MATERIALIZED_OUTPUTS], root=root)
        return {
            "status": "clustered_inference_materialized_unfinalized",
            "authority": authority, "site_loss_rows": len(first["site_level_losses"]),
            "pairwise_effect_rows": len(first["pairwise_effects"]),
            "multiplicity_rows": len(first["multiplicity_report"]),
            "bootstrap_summary_rows": len(first["bootstrap_summary"]),
            "bootstrap_distribution_rows": len(first["bootstrap_distributions"]),
            "next_required": ".venv/bin/dvc add reports/closure_v2/05_inference/bootstrap_distributions.parquet then --finalize",
        }
    finally:
        guard.rmdir()


def _report_bytes(root: Path) -> bytes:
    effects = pd.read_csv(_require_regular(root, PAIRWISE_EFFECTS))
    multiplicity = pd.read_csv(_require_regular(root, MULTIPLICITY))
    registered = effects.loc[effects["registered_hypothesis_id"].notna(), [
        "registered_hypothesis_id", "comparison_id", "horizon_months", "metric",
        "estimate", "ci95_lower", "ci95_upper", "adjudication",
        "shared_success_rows", "shared_success_clusters",
    ]]
    lines = [
        "# Closure V2 statistical inference report", "",
        "P14 used the five-seed family mean already frozen in P13. It resampled `source_id::site_id` clusters with replacement for 2,000 paired bootstrap replicates and never treated seeds as ecological observations.", "",
        "## Registered fresh-primary contrasts", "", registered.to_markdown(index=False), "",
        "## Multiplicity", "",
        "All registered Holm universes are retained (A=3, B=3, C=6). The protocol did not predeclare a bootstrap p-value formula or directional alternative. Therefore raw and Holm-adjusted p-values remain null; no post-outcome p-value convention was introduced. Scientific adjudication uses the preregistered percentile IC95 rules.", "",
        multiplicity.to_markdown(index=False), "",
        "## Scope", "",
        "`fresh_primary` supports internal evaluation on WQP monitoring locations unused by V1, not external validation. `legacy_posthoc` remains retrospective/complementary. Cohorts and observation/site-weighted estimands were never pooled. No global winner, equivalence, field causality, or official recommendation is claimed.", "",
        f"- P13 authority commit: `{P13_COMMIT}`",
        f"- P13 evaluation manifest SHA-256: `{sha256_file(root / EVALUATION_MANIFEST)}`",
        f"- inference script SHA-256: `{sha256_file(root / SCRIPT_PATH)}`", "",
    ]
    return "\n".join(lines).encode("utf-8")


def _record_from_bytes(relative: Path, payload: bytes, role: str) -> dict[str, Any]:
    return {
        "path": relative.as_posix(), "role": role, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def finalize(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if (root / REPORT).exists() or (root / REPORT).is_symlink():
        raise InferenceError("P14 report already exists")
    for path in (*MATERIALIZED_OUTPUTS, BOOTSTRAP_POINTER):
        _require_regular(root, path)
    pointer = yaml.safe_load((root / BOOTSTRAP_POINTER).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise InferenceError("P14 bootstrap DVC pointer is malformed")
    physical = root / BOOTSTRAP_DISTRIBUTIONS
    if (
        outs[0].get("path") != BOOTSTRAP_DISTRIBUTIONS.name
        or outs[0].get("size") != physical.stat().st_size
        or outs[0].get("md5") != md5_file(physical)
    ):
        raise InferenceError("P14 bootstrap pointer does not bind its physical table")
    bootstrap = pq.read_table(physical).to_pandas()
    if len(bootstrap) != 96_000 or bootstrap["replicate"].min() != 1 or bootstrap["replicate"].max() != 2000:
        raise InferenceError("P14 bootstrap distribution denominator drifted")
    multiplicity = pd.read_csv(root / MULTIPLICITY)
    if multiplicity.groupby("holm_family").size().to_dict() != {"A": 3, "B": 3, "C": 6}:
        raise InferenceError("P14 final Holm universe was reduced")
    report = _report_bytes(root)
    _exclusive_bundle([(REPORT, report)], root=root)
    return {
        "status": "clustered_inference_completed",
        "bootstrap_rows": len(bootstrap), "bootstrap_dvc_md5": outs[0]["md5"],
        "bootstrap_dvc_size": outs[0]["size"],
        "report_sha256": sha256_file(root / REPORT),
        "holm_universes": {"A": 3, "B": 3, "C": 6},
        "bootstrap_p_value_predeclared": False,
    }


def complete_manifest(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Publish the P14 experiment manifest last without recomputing inference."""
    if (root / INFERENCE_MANIFEST).exists() or (root / INFERENCE_MANIFEST).is_symlink():
        raise InferenceError("P14 inference manifest already exists")
    for path in (*MATERIALIZED_OUTPUTS, BOOTSTRAP_POINTER, REPORT):
        _require_regular(root, path)
    pointer = yaml.safe_load((root / BOOTSTRAP_POINTER).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise InferenceError("P14 bootstrap pointer is malformed before manifest completion")
    physical = root / BOOTSTRAP_DISTRIBUTIONS
    if (
        outs[0].get("path") != BOOTSTRAP_DISTRIBUTIONS.name
        or outs[0].get("size") != physical.stat().st_size
        or outs[0].get("md5") != md5_file(physical)
    ):
        raise InferenceError("P14 physical bootstrap binding drifted before manifest completion")
    effects = pd.read_csv(root / PAIRWISE_EFFECTS)
    multiplicity = pd.read_csv(root / MULTIPLICITY)
    summary = pd.read_csv(root / BOOTSTRAP_SUMMARY)
    bootstrap = pq.read_table(physical).to_pandas()
    if (
        len(effects) != 48 or len(summary) != 48 or len(bootstrap) != 96_000
        or multiplicity.groupby("holm_family").size().to_dict() != {"A": 3, "B": 3, "C": 6}
        or not effects["raw_p_value"].isna().all()
        or not effects["holm_p_value"].isna().all()
    ):
        raise InferenceError("P14 tables failed pre-manifest validation")
    report_payload = _report_bytes(root)
    manifest = {
        "schema_version": "closure_v2_inference_manifest_v1",
        "experiment_id": "closure_v2", "phase": "P14", "status": "completed",
        "authority_commit": P13_COMMIT,
        "script": _record_from_bytes(SCRIPT_PATH, (root / SCRIPT_PATH).read_bytes(), "clustered_inference_runner"),
        "inputs": [
            {
                "path": path.as_posix(), "role": role,
                "bytes": (root / path).stat().st_size, "sha256": sha256_file(root / path),
            }
            for path, role in (
                (ANALYSIS_PLAN, "locked_analysis_plan"),
                (MODEL_LOCK, "locked_model_registry"),
                (EVALUATION_MANIFEST, "p13_evaluation_manifest"),
                (PREDICTIONS_POINTER, "p13_prediction_pointer"),
            )
        ],
        "data_artifact": {
            "path": BOOTSTRAP_DISTRIBUTIONS.as_posix(), "role": "bootstrap_distributions",
            "bytes": physical.stat().st_size, "sha256": sha256_file(physical),
            "dvc_pointer": BOOTSTRAP_POINTER.as_posix(),
            "dvc_md5": outs[0]["md5"], "dvc_size": outs[0]["size"],
        },
        "outputs": [
            {
                "path": path.as_posix(), "role": "inference_output",
                "bytes": (root / path).stat().st_size, "sha256": sha256_file(root / path),
            }
            for path in (SITE_LOSSES, PAIRWISE_EFFECTS, MULTIPLICITY, BOOTSTRAP_SUMMARY, BOOTSTRAP_POINTER)
        ] + [_record_from_bytes(REPORT, report_payload, "inference_output")],
        "bootstrap_replicates_per_contrast": BOOTSTRAP_REPLICATES,
        "bootstrap_distribution_rows": len(bootstrap),
        "pairwise_effect_rows": len(effects), "bootstrap_summary_rows": len(summary),
        "cluster_unit": "source_id_plus_site_id",
        "estimands": list(ESTIMANDS), "evaluation_cohorts": list(COHORTS),
        "seeds_used_as_ecological_replicates": False,
        "holm_universes": {"A": 3, "B": 3, "C": 6},
        "holm_universe_reduced": False,
        "bootstrap_p_value_predeclared": False,
        "raw_p_values_computed": False, "holm_p_values_computed": False,
        "p_value_absence_reason": "bootstrap_p_value_formula_and_directional_alternative_not_predeclared",
        "cohorts_pooled": False, "estimands_pooled": False,
        "refit_performed": False, "recalibration_performed": False,
        "reproducibility_check": "two_full_deterministic_materializations_byte_identical",
        "manifest_written_last": True,
    }
    old_report = root / REPORT
    archive_root = root / "tmp" / f"p14_pre_manifest_report_{sha256_file(old_report)}"
    if archive_root.exists() or archive_root.is_symlink():
        raise InferenceError("P14 pre-manifest report archive already exists")
    archived_report = archive_root / REPORT
    archived_report.parent.mkdir(parents=True, exist_ok=True)
    inode = old_report.stat().st_ino
    os.link(old_report, archived_report)
    if old_report.stat().st_ino != inode:
        raise InferenceError("P14 report changed during archival")
    old_report.unlink()
    _exclusive_bundle(
        [(REPORT, report_payload), (INFERENCE_MANIFEST, canonical_json_bytes(manifest))],
        root=root,
    )
    return {
        "status": "clustered_inference_manifest_completed",
        "manifest_sha256": sha256_file(root / INFERENCE_MANIFEST),
        "report_sha256": sha256_file(root / REPORT),
        "archived_pre_manifest_report": archive_root.relative_to(root).as_posix(),
        "manifest_written_last": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute", action="store_true")
    group.add_argument("--finalize", action="store_true")
    group.add_argument("--complete-manifest", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = (
        execute() if args.execute
        else finalize() if args.finalize
        else complete_manifest() if args.complete_manifest
        else preflight()
    )
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
