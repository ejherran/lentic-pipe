from __future__ import annotations

from pathlib import Path

import pytest

from src.experiments.closure_v2 import lock_models


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
