from __future__ import annotations

from pathlib import Path

import pytest

from src.experiments.closure_v2 import lock_models
from src.experiments.closure_v2 import activate_evaluation


def test_model_lock_schema_keeps_evaluation_false() -> None:
    lock = {
        "authorization": {
            "evaluation_authorized": False,
            "post_2021_outcomes_authorized": False,
            "activation_required": True,
            "activation_one_shot": True,
        }
    }
    assert lock["authorization"]["evaluation_authorized"] is False
    assert lock["authorization"]["activation_required"] is True


def test_effective_loader_fails_without_annotated_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in (lock_models.MODEL_LOCK_PATH, lock_models.MODEL_LOCK_MANIFEST_PATH):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(lock_models, "_git", lambda *args, **kwargs: "commit")
    with pytest.raises(lock_models.ModelLockError, match="annotated tag"):
        lock_models.load_effective_model_lock(root=tmp_path)


def test_sealed_commands_do_not_include_refit_or_recalibration(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "sealed_commands": [
            ".venv/bin/python -m src.experiments.closure_v2.build_evaluation_inputs --execute",
            ".venv/bin/python -m src.experiments.closure_v2.activate_evaluation --execute",
            ".venv/bin/python -m src.experiments.closure_v2.evaluate_models --execute",
        ]
    }
    assert all("refit" not in command and "recalibr" not in command for command in payload["sealed_commands"])


def test_p11_is_separate_from_one_shot_activation() -> None:
    from src.experiments.closure_v2 import build_evaluation_inputs

    parser = build_evaluation_inputs.build_parser()
    p11 = parser.parse_args(["--execute"])
    assert p11.execute is True
    assert not hasattr(p11, "activate")


def test_activation_line_is_canonical_and_single_line() -> None:
    payload = {"z": 1, "a": "fresh_primary"}
    assert activate_evaluation._canonical_line(payload) == b'{"a":"fresh_primary","z":1}\n'


def test_activation_log_rejects_duplicate_activation(tmp_path: Path) -> None:
    path = tmp_path / "outcome_access_log.jsonl"
    first = {"event_index": 0, "event_type": "evaluation_activation"}
    second = {"event_index": 1, "event_type": "evaluation_activation"}
    path.write_bytes(
        activate_evaluation._canonical_line(first)
        + activate_evaluation._canonical_line(second)
    )
    with pytest.raises(activate_evaluation.EvaluationActivationError, match="one activation"):
        activate_evaluation._parse_log(path)


def test_activation_log_rejects_second_execution(tmp_path: Path) -> None:
    path = tmp_path / "outcome_access_log.jsonl"
    events = [
        {"event_index": 0, "event_type": "evaluation_activation"},
        {"event_index": 1, "event_type": "evaluation_execution_started"},
        {"event_index": 2, "event_type": "evaluation_execution_started"},
    ]
    path.write_bytes(b"".join(activate_evaluation._canonical_line(event) for event in events))
    with pytest.raises(activate_evaluation.EvaluationActivationError, match="more than once"):
        activate_evaluation._parse_log(path)


def test_execute_activation_is_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = {
        "event_index": 0,
        "event_type": "evaluation_activation",
        "activation_id": "a" * 64,
        "activation_base_commit": "b" * 40,
        "contract_sha256": "c" * 64,
    }
    monkeypatch.setattr(
        activate_evaluation,
        "build_activation_event",
        lambda *, root: event,
    )
    first = activate_evaluation.execute_activation(root=tmp_path)
    assert first["executions_consumed"] == 0
    with pytest.raises(activate_evaluation.EvaluationActivationError, match="already exists"):
        activate_evaluation.execute_activation(root=tmp_path)
