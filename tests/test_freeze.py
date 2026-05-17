from __future__ import annotations

from src.data.freeze import EXACT_GENERATION_COMMANDS


def test_data_freeze_generation_commands_use_incremental_raw_manifest() -> None:
    assert ".venv/bin/python src/data/validate_sources.py" in EXACT_GENERATION_COMMANDS
    assert ".venv/bin/python src/data/raw_manifest.py --reuse-existing" in EXACT_GENERATION_COMMANDS
    assert ".venv/bin/python src/data/raw_manifest.py" not in EXACT_GENERATION_COMMANDS
