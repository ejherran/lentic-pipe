from __future__ import annotations

from pathlib import Path

from src.data.validate_sources import validate_config


def _config(raw_path: Path) -> dict:
    script_path = tmp_script(raw_path.parent)
    return {
        "source_contract": {
            "required_fields": [
                "source_id",
                "raw_path",
                "local_raw_path",
                "adapter",
                "role",
                "source_type",
                "access_policy",
                "dvc_track",
                "license",
                "provenance_status",
            ]
        },
        "sources": {
            "wqp": {
                "source_id": "wqp",
                "source_name": "Water Quality Portal",
                "raw_path": raw_path.as_posix(),
                "local_raw_path": raw_path.as_posix(),
                "adapter": "wqp_streaming",
                "role": "large_public_lentic_physchem_source",
                "source_type": "public_api_export",
                "access_policy": "public_original_private_mirror",
                "dvc_track": True,
                "license": "provider_terms",
                "provenance_status": "documented",
                "acquisition": {"route": "script", "script_hint": script_path.as_posix()},
            }
        },
    }


def tmp_script(parent: Path) -> Path:
    script_path = parent / "download_wqp_results.py"
    script_path.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    return script_path


def test_validate_sources_accepts_complete_existing_source(tmp_path: Path) -> None:
    raw_path = tmp_path / "wqp"
    raw_path.mkdir()

    assert validate_config(_config(raw_path)) == []


def test_validate_sources_reports_missing_raw_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"

    errors = validate_config(_config(missing_path))

    assert f"wqp: raw_path does not exist: {missing_path}" in errors


def test_validate_sources_reports_missing_script_hint(tmp_path: Path) -> None:
    raw_path = tmp_path / "wqp"
    raw_path.mkdir()
    config = _config(raw_path)
    config["sources"]["wqp"]["acquisition"]["script_hint"] = (tmp_path / "missing.py").as_posix()

    errors = validate_config(config)

    assert f"wqp: acquisition.script_hint does not exist: {tmp_path / 'missing.py'}" in errors
