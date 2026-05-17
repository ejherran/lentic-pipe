from __future__ import annotations

import json
from pathlib import Path

from src.data.raw_manifest import build_records, build_records_with_existing, write_source_catalog


def test_raw_manifest_paths_hash_metadata_without_changing_adapter_raw_path(tmp_path: Path) -> None:
    source_dir = tmp_path / "aquamatch"
    source_dir.mkdir()
    csv_path = source_dir / "chla_harmonized_final.csv"
    metadata_path = source_dir / "metadata.xml"
    readme_path = source_dir / "README.pdf"
    csv_path.write_text("parameter,value\nchlorophyll,1.0\n", encoding="utf-8")
    metadata_path.write_text("<eml packageId='edi.1756.2' />\n", encoding="utf-8")
    readme_path.write_bytes(b"%PDF-1.4\n")

    config = {
        "sources": {
            "aquamatch_chla": {
                "source_name": "AquaMatch",
                "adapter": "aquamatch_chla",
                "role": "chlorophyll_auxiliary_source",
                "license": "cc0-1.0",
                "provenance_status": "documented",
                "local_raw_path": source_dir.as_posix(),
                "raw_path": csv_path.as_posix(),
                "raw_manifest_paths": [
                    csv_path.as_posix(),
                    metadata_path.as_posix(),
                    readme_path.as_posix(),
                    csv_path.as_posix(),
                ],
            }
        }
    }

    records = build_records(config)

    assert [record.relative_to_source for record in records] == [
        "chla_harmonized_final.csv",
        "metadata.xml",
        "README.pdf",
    ]
    assert all(record.source_id == "aquamatch_chla" for record in records)
    assert all(record.sha256 for record in records)


def test_source_catalog_preserves_extended_source_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "aquamatch"
    source_dir.mkdir()
    csv_path = source_dir / "chla_harmonized_final.csv"
    csv_path.write_text("parameter,value\nchlorophyll,1.0\n", encoding="utf-8")
    config = {
        "sources": {
            "aquamatch_chla": {
                "source_name": "AquaMatch",
                "source_type": "authenticated_public_repository_package",
                "access_policy": "public_domain_original_authenticated_private_mirror",
                "adapter": "aquamatch_chla",
                "role": "chlorophyll_auxiliary_source",
                "format": {"kind": "csv", "main_file": "chla_harmonized_final.csv"},
                "acquisition": {"package_id": "edi.1756.2"},
                "license": "cc0-1.0",
                "provenance_status": "documented",
                "local_raw_path": source_dir.as_posix(),
                "raw_path": csv_path.as_posix(),
                "raw_manifest_paths": [csv_path.as_posix()],
                "dvc_track": True,
            }
        }
    }
    records = build_records(config)
    catalog_path = tmp_path / "source_catalog.json"

    write_source_catalog(config, records, catalog_path)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    source = catalog["sources"]["aquamatch_chla"]
    assert source["source_type"] == "authenticated_public_repository_package"
    assert source["acquisition"]["package_id"] == "edi.1756.2"
    assert source["format"]["main_file"] == "chla_harmonized_final.csv"
    assert source["raw_manifest_paths"] == [csv_path.as_posix()]


def test_raw_manifest_can_reuse_existing_hashes(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "wqp"
    source_dir.mkdir()
    raw_path = source_dir / "wqp_results.csv"
    raw_path.write_text("a,b\n1,2\n", encoding="utf-8")
    initial_records = build_records(
        {
            "sources": {
                "wqp": {
                    "source_name": "WQP",
                    "adapter": "wqp_streaming",
                    "role": "source",
                    "license": "terms",
                    "provenance_status": "documented",
                    "local_raw_path": source_dir.as_posix(),
                    "raw_path": source_dir.as_posix(),
                }
            }
        }
    )
    existing = {
        record.path: {
            "path": record.path,
            "size_bytes": str(record.size_bytes),
            "modified_time_utc": record.modified_time_utc,
            "sha256": record.sha256,
        }
        for record in initial_records
    }

    def fail_hash(_path: Path) -> str:
        raise AssertionError("sha256_file should not be called for unchanged files")

    monkeypatch.setattr("src.data.raw_manifest.sha256_file", fail_hash)
    records, stats = build_records_with_existing(
        {
            "sources": {
                "wqp": {
                    "source_name": "WQP",
                    "adapter": "wqp_streaming",
                    "role": "source",
                    "license": "terms",
                    "provenance_status": "documented",
                    "local_raw_path": source_dir.as_posix(),
                    "raw_path": source_dir.as_posix(),
                }
            }
        },
        existing,
    )

    assert records[0].sha256 == initial_records[0].sha256
    assert stats == {"computed_hashes": 0, "reused_hashes": 1}


def test_raw_manifest_excludes_local_cache_directories(tmp_path: Path) -> None:
    source_dir = tmp_path / "lakebed"
    data_dir = source_dir / "Data"
    cache_dir = source_dir / ".cache" / "huggingface"
    data_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    raw_path = data_dir / "lake.parquet"
    cache_path = cache_dir / "download.metadata"
    raw_path.write_text("raw-data\n", encoding="utf-8")
    cache_path.write_text("cache-metadata\n", encoding="utf-8")

    records = build_records(
        {
            "sources": {
                "lakebed_us_cse": {
                    "source_name": "LakeBeD",
                    "adapter": "lakebed_us_cse",
                    "role": "source",
                    "license": "cc-by-4.0",
                    "provenance_status": "documented",
                    "local_raw_path": source_dir.as_posix(),
                    "raw_path": source_dir.as_posix(),
                }
            }
        }
    )

    assert [record.relative_to_source for record in records] == ["Data/lake.parquet"]
