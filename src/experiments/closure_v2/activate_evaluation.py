#!/usr/bin/env python
"""Create and validate the one-shot Closure V2 evaluation activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from src.experiments.closure_contract import ClosureContractError, load_json_mapping
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.hashing import canonical_json_bytes, file_record, sha256_file
from src.experiments.closure_v2.lock_models import (
    MODEL_LOCK_MANIFEST_PATH,
    MODEL_LOCK_PATH,
    MODEL_LOCK_TAG,
)


ACTIVATION_SCRIPT = Path("src/experiments/closure_v2/activate_evaluation.py")
OUTCOME_LOG = Path("reports/closure_v2/00_protocol/outcome_access_log.jsonl")
COHORT_DECISION = Path("reports/closure_v2/00_protocol/fresh_cohort_decision.json")
COHORT_MANIFEST = Path("reports/closure_v2/00_protocol/fresh_cohort_manifest.json")
INPUT_MANIFEST = Path("reports/closure_v2/01_surface/locked_evaluation_input_manifest.json")
BRANCH_REF = "origin/closure-v2"
EXPECTED_LOCATIONS = 137
EXPECTED_ORIGINS = 2_286
EXPECTED_KEY_DIGEST = "347bb61867813327351cdc4c896cd50695ab02a84fa52d256a31e8a280323952"


class EvaluationActivationError(ClosureContractError):
    """Raised when the one-shot evaluation authority is not exact."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise EvaluationActivationError(f"Required regular file is absent: {relative}")
    return path


def _git_bytes(commit: str, relative: Path, *, root: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative.as_posix()}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _canonical_line(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _sha256_mapping(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _model_lock_authority(*, root: Path) -> dict[str, Any]:
    try:
        tag_type = _git("cat-file", "-t", f"refs/tags/{MODEL_LOCK_TAG}", root=root)
    except subprocess.CalledProcessError as error:
        raise EvaluationActivationError("Annotated model-lock tag is absent") from error
    if tag_type != "tag":
        raise EvaluationActivationError("Model-lock authority must be an annotated tag")
    model_commit = _git("rev-parse", f"{MODEL_LOCK_TAG}^{{}}", root=root)
    head = _git("rev-parse", "HEAD", root=root)
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", model_commit, head],
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise EvaluationActivationError("Model-lock commit is not an ancestor of P11")
    for relative in (MODEL_LOCK_PATH, MODEL_LOCK_MANIFEST_PATH):
        live = _require_regular(root, relative).read_bytes()
        if live != _git_bytes(model_commit, relative, root=root):
            raise EvaluationActivationError(f"Live model-lock bytes drifted: {relative}")
    lock = load_json_mapping(root / MODEL_LOCK_PATH)
    authorization = lock.get("authorization")
    if not isinstance(authorization, Mapping):
        raise EvaluationActivationError("Model-lock authorization is malformed")
    if authorization.get("evaluation_authorized") is not False:
        raise EvaluationActivationError("Model lock must remain inactive before P12")
    if authorization.get("activation_required") is not True:
        raise EvaluationActivationError("Model lock does not require P12 activation")
    return {
        "tag": MODEL_LOCK_TAG,
        "commit": model_commit,
        "sha256": sha256_file(root / MODEL_LOCK_PATH),
    }


def _published_input_bundle(*, root: Path) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", BRANCH_REF, root=root)
    if head != remote:
        raise EvaluationActivationError("P11 HEAD and origin/closure-v2 must coincide")
    parent_line = _git("rev-list", "--parents", "-n", "1", head, root=root).split()
    if len(parent_line) != 2:
        raise EvaluationActivationError("P11 must be a single-parent publication commit")
    for relative in (COHORT_DECISION, COHORT_MANIFEST, INPUT_MANIFEST):
        live = _require_regular(root, relative).read_bytes()
        if live != _git_bytes(head, relative, root=root):
            raise EvaluationActivationError(f"Live P11 authority differs from HEAD: {relative}")
    decision = load_json_mapping(root / COHORT_DECISION)
    cohort = load_json_mapping(root / COHORT_MANIFEST)
    inputs = load_json_mapping(root / INPUT_MANIFEST)
    expected = {
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "candidate_location_count": EXPECTED_LOCATIONS,
        "intent_origins_per_horizon": EXPECTED_ORIGINS,
        "candidate_key_digest_sha256": EXPECTED_KEY_DIGEST,
    }
    for name, payload in (("cohort", cohort), ("input", inputs)):
        for key, value in expected.items():
            if payload.get(key) != value:
                raise EvaluationActivationError(f"P11 {name} contract drifted: {key}")
        if payload.get("outcome_values_opened") is not False:
            raise EvaluationActivationError(f"P11 {name} reports prior outcome access")
        if payload.get("target_availability_inspected") is not False:
            raise EvaluationActivationError(f"P11 {name} reports prior availability access")
    if decision.get("evaluation_cohort") != "fresh_primary":
        raise EvaluationActivationError("Fresh cohort decision drifted")
    routes = decision.get("routes")
    if not isinstance(routes, Mapping):
        raise EvaluationActivationError("Fresh cohort routes are malformed")
    fresh = routes.get("fresh_location")
    if not isinstance(fresh, Mapping) or fresh.get("status") != "selected":
        raise EvaluationActivationError("fresh_location is not the selected P11 route")
    return {
        "commit": head,
        "parent": parent_line[1],
        "decision_sha256": sha256_file(root / COHORT_DECISION),
        "cohort_manifest_sha256": sha256_file(root / COHORT_MANIFEST),
        "input_manifest_sha256": sha256_file(root / INPUT_MANIFEST),
    }


def build_activation_event(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build the deterministic first JSONL event without opening outcomes."""
    if (root / OUTCOME_LOG).exists() or (root / OUTCOME_LOG).is_symlink():
        raise EvaluationActivationError("P12 outcome access log already exists")
    model_lock = _model_lock_authority(root=root)
    input_bundle = _published_input_bundle(root=root)
    if input_bundle["parent"] != model_lock["commit"]:
        raise EvaluationActivationError("P11 must be the direct child of the model-lock commit")
    script = file_record(root / ACTIVATION_SCRIPT, root=root, role="evaluation_activation_writer")
    contract = {
        "schema_version": "closure_v2_evaluation_activation_contract_v1",
        "experiment_id": "closure_v2",
        "model_lock": model_lock,
        "input_bundle": input_bundle,
        "activation_script": script,
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "candidate_location_count": EXPECTED_LOCATIONS,
        "intent_origins_per_horizon": EXPECTED_ORIGINS,
        "candidate_key_digest_sha256": EXPECTED_KEY_DIGEST,
        "execution_limit": 1,
        "append_only": True,
        "replacement_for_missing_target": False,
        "refit_authorized": False,
        "recalibration_authorized": False,
    }
    contract_sha256 = _sha256_mapping(contract)
    activation_id = hashlib.sha256(
        f"closure_v2\x00{input_bundle['commit']}\x00{contract_sha256}".encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "closure_v2_outcome_access_event_v1",
        "experiment_id": "closure_v2",
        "event_index": 0,
        "event_type": "evaluation_activation",
        "activation_id": activation_id,
        "activation_base_commit": input_bundle["commit"],
        "model_lock_commit": model_lock["commit"],
        "model_lock_tag": model_lock["tag"],
        "model_lock_sha256": model_lock["sha256"],
        "contract": contract,
        "contract_sha256": contract_sha256,
        "authorization": {
            "evaluation_authorized": True,
            "post_2021_outcome_access_authorized": True,
            "execution_limit": 1,
            "executions_consumed": 0,
            "one_shot": True,
            "append_only": True,
            "effective_after_publication": True,
        },
        "outcome_values_opened": False,
        "target_availability_inspected": False,
        "benchmark_executed": False,
        "refit_performed": False,
        "recalibration_performed": False,
        "replacement_used": False,
    }


def _parse_log(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise EvaluationActivationError("Outcome access log must be a regular file")
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise EvaluationActivationError("Outcome access log must end with LF")
    events: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(keepends=True)):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvaluationActivationError("Outcome access log contains invalid JSON") from error
        if not isinstance(payload, Mapping):
            raise EvaluationActivationError("Outcome access event must be a mapping")
        event = dict(payload)
        if line != _canonical_line(event):
            raise EvaluationActivationError("Outcome access event is not canonical JSONL")
        if event.get("event_index") != index:
            raise EvaluationActivationError("Outcome access event indices are not contiguous")
        events.append(event)
    if events[0].get("event_type") != "evaluation_activation":
        raise EvaluationActivationError("First outcome access event must be activation")
    if sum(event.get("event_type") == "evaluation_activation" for event in events) != 1:
        raise EvaluationActivationError("Outcome access log must contain one activation")
    started = sum(event.get("event_type") == "evaluation_execution_started" for event in events)
    if started > 1:
        raise EvaluationActivationError("One-shot evaluation was consumed more than once")
    return events


def execute_activation(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    destination = root / OUTCOME_LOG
    if destination.exists() or destination.is_symlink():
        raise EvaluationActivationError("P12 outcome access log already exists")
    event = build_activation_event(root=root)
    payload = _canonical_line(event)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o644)
    except FileExistsError as error:
        raise EvaluationActivationError("P12 outcome access log already exists") from error
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise EvaluationActivationError("Short write while creating activation log")
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        if destination.is_file() and not destination.is_symlink():
            destination.unlink()
        raise
    else:
        os.close(descriptor)
    events = _parse_log(destination)
    if events != [event]:
        raise EvaluationActivationError("Activation log failed post-write validation")
    return {
        "status": "evaluation_activation_written_unpublished",
        "activation_id": event["activation_id"],
        "activation_base_commit": event["activation_base_commit"],
        "contract_sha256": event["contract_sha256"],
        "execution_limit": 1,
        "executions_consumed": 0,
        "outcome_values_opened": False,
        "benchmark_executed": False,
        "effective_after_publication": True,
    }


def load_effective_activation(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    events = _parse_log(_require_regular(root, OUTCOME_LOG))
    activation = events[0]
    contract = activation.get("contract")
    if not isinstance(contract, Mapping) or activation.get("contract_sha256") != _sha256_mapping(contract):
        raise EvaluationActivationError("Activation contract hash drifted")
    base_commit = str(activation.get("activation_base_commit", ""))
    current_head = _git("rev-parse", "HEAD", root=root)
    remote = _git("rev-parse", BRANCH_REF, root=root)
    if current_head != remote:
        raise EvaluationActivationError("Activation HEAD and origin/closure-v2 must coincide")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_commit, current_head],
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise EvaluationActivationError("Activation base commit is not an ancestor")
    publication_commit = _git("log", "-1", "--format=%H", "--", OUTCOME_LOG.as_posix(), root=root)
    if not publication_commit:
        raise EvaluationActivationError("Activation log is not published in Git")
    if _git_bytes(publication_commit, OUTCOME_LOG, root=root) != (root / OUTCOME_LOG).read_bytes():
        raise EvaluationActivationError("Live activation log differs from its publication commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", publication_commit, remote],
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode != 0:
        raise EvaluationActivationError("Activation publication is absent from remote history")
    consumed = sum(event.get("event_type") == "evaluation_execution_started" for event in events)
    return {
        "status": "evaluation_activation_effective",
        "activation_id": activation["activation_id"],
        "activation_base_commit": base_commit,
        "publication_commit": publication_commit,
        "contract_sha256": activation["contract_sha256"],
        "execution_limit": 1,
        "executions_consumed": consumed,
        "executions_remaining": 1 - consumed,
        "outcome_access_authorized": consumed == 0,
    }


def preflight(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    event = build_activation_event(root=root)
    return {
        "status": "ready_to_activate",
        "activation_id": event["activation_id"],
        "activation_base_commit": event["activation_base_commit"],
        "contract_sha256": event["contract_sha256"],
        "execution_limit": 1,
        "outcome_values_opened": False,
        "benchmark_executed": False,
        "writes_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute", action="store_true")
    group.add_argument("--check-effective", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.execute:
        result = execute_activation()
    elif args.check_effective:
        result = load_effective_activation()
    else:
        result = preflight()
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
