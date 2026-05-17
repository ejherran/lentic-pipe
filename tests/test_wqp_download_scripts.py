from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

from data.scripts.wqp_download_common import WqpDownloadConfig, build_url, deduplicate_csv, merge_chunks

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "data/scripts"


def _config(tmp_path: Path) -> WqpDownloadConfig:
    return WqpDownloadConfig(
        label="wqp_results",
        base_url="https://www.waterqualitydata.us/wqx3/Result/search",
        base_params=(("countrycode", "US"), ("providers", "NWIS"), ("providers", "STORET")),
        final_file=tmp_path / "raw/wqp_results.csv",
        state_file=tmp_path / "raw/wqp_results_state.json",
        chunk_dir=tmp_path / "cache/results",
        user_agent="test-agent",
    )


def test_wqp_url_uses_expected_date_format_and_repeated_provider_params(tmp_path: Path) -> None:
    url = build_url(_config(tmp_path), date(1970, 1, 1), date(2026, 5, 11))

    assert url.startswith("https://www.waterqualitydata.us/wqx3/Result/search?")
    assert "countrycode=US" in url
    assert "providers=NWIS" in url
    assert "providers=STORET" in url
    assert "startDateLo=01-01-1970" in url
    assert "startDateHi=05-11-2026" in url


def test_merge_chunks_writes_single_header_and_filters_incomplete_marker(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.chunk_dir.mkdir(parents=True)
    (config.chunk_dir / "chunk_1970-01-01_1970-01-01.csv").write_text(
        "a,b\n1,2\nINCOMPLETE DATA,\n",
        encoding="utf-8",
    )
    (config.chunk_dir / "chunk_1970-01-02_1970-01-02.csv").write_text("a,b\n3,4\n", encoding="utf-8")

    rows = merge_chunks(config, config.final_file)

    assert rows == 2
    assert config.final_file.read_text(encoding="utf-8").splitlines() == ["a,b", "1,2", "3,4"]


def test_deduplicate_csv_uses_composite_station_key(tmp_path: Path) -> None:
    source = tmp_path / "stations_merged.csv"
    target = tmp_path / "wqp_stations.csv"
    source.write_text(
        "Org_Identifier,Location_Identifier,Location_Name\n"
        "A,site-1,first\n"
        "A,site-1,duplicate\n"
        "B,site-1,different-org\n",
        encoding="utf-8",
    )

    rows = deduplicate_csv(source, target, ("Org_Identifier", "Location_Identifier"))

    assert rows == 2
    assert target.read_text(encoding="utf-8").splitlines() == [
        "Org_Identifier,Location_Identifier,Location_Name",
        "A,site-1,first",
        "B,site-1,different-org",
    ]


def test_download_entrypoints_are_importable_without_running_downloads() -> None:
    script_names = [
        "download_wqp_results.py",
        "download_wqp_activity.py",
        "download_wqp_stations.py",
        "download_lakebed_us_cse.py",
    ]

    for script_name in script_names:
        script_path = SCRIPT_DIR / script_name
        spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
