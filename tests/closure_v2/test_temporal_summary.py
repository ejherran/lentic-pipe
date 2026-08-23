from __future__ import annotations

from pathlib import Path

import pytest

from src.experiments.closure_v2 import summarize_temporal


def test_models_pointer_requires_locked_directory_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "models.dvc").write_text(
        "outs:\n- md5: abc.dir\n  size: 20\n  nfiles: 2\n  hash: md5\n  path: models\n",
        encoding="utf-8",
    )

    class Result:
        stdout = "Data and pipelines are up to date.\n"

    monkeypatch.setattr(summarize_temporal.subprocess, "run", lambda *args, **kwargs: Result())
    record = summarize_temporal.validate_models_pointer(root=tmp_path)
    assert record["directory_md5"] == "abc.dir"
    assert record["directory_files"] == 2


def test_models_pointer_rejects_non_directory_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "models.dvc").write_text(
        "outs:\n- md5: abc\n  size: 20\n  nfiles: 2\n  hash: md5\n  path: models\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(summarize_temporal.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(summarize_temporal.TemporalTrainingError, match="contract drifted"):
        summarize_temporal.validate_models_pointer(root=tmp_path)
