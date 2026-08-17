from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.reporting import closure_synthesis_contract as contract_module


ROOT = Path(__file__).resolve().parents[1]


def _write_contract(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "contract.yaml"
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def test_real_contract_is_exact_outcome_free_freeze() -> None:
    contract = contract_module.load_contract(root=ROOT)

    assert contract.closure_source_commit == (
        "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
    )
    assert len(contract.allowed_inputs) == 83
    assert len(contract.output_paths) == 24
    assert contract.output_paths[-1].endswith("synthesis_bundle_manifest.json")
    assert contract.required_unavailable_models == ("P0", "P1", "A2")
    assert contract.required_hypotheses == ("H1", "H2", "H3", "H4", "H5a", "H5b")
    assert dict(contract.holm_universes) == {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1}
    assert contract.final_closure_row_count == 130
    assert contract.claim_evidence_row_count == 20
    assert dict(contract.table_row_counts) == {
        "T01": 99,
        "T02": 33,
        "T03": 198,
        "T04": 24,
        "T05": 11,
        "T06": 48,
        "T07": 31,
        "T08": 92,
        "T09": 7,
        "T10": 36,
        "T11": 87,
        "T12": 5,
    }

    paths = contract.allowed_input_paths
    assert paths == tuple(sorted(paths))
    assert len(paths) == len(set(paths))
    assert not any(path.startswith(("private/", "data/targets/")) for path in paths)
    assert not any(path.endswith((".parquet", ".jsonl", ".md", ".xml")) for path in paths)
    assert "reports/closure_v1/00_protocol/outcome_access_log.jsonl" not in paths
    assert "data/closure_v1/predictions_long.parquet.dvc" in paths
    assert [spec.path for spec in contract.allowed_inputs if spec.allow_empty] == [
        "reports/closure_v1/04_trophic/nla_semantic_metrics.csv"
    ]
    assert set(contract.artifact_captions) == {
        *(f"T{index:02d}" for index in range(1, 13)),
        *(f"F{index:02d}" for index in range(1, 9)),
    }


def test_schema_is_valid_json_and_binds_the_contract_identity() -> None:
    schema_path = ROOT / contract_module.DEFAULT_SCHEMA_PATH
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["contract_version"]["const"] == (
        "closure_v1_phase4_synthesis_v1"
    )
    assert schema["properties"]["closure_source_commit"]["const"] == (
        "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
    )


def test_schema_seals_nested_topology_outputs_and_adjudication() -> None:
    schema = json.loads(
        (ROOT / contract_module.DEFAULT_SCHEMA_PATH).read_text(encoding="utf-8")
    )
    contract = yaml.safe_load(
        (ROOT / contract_module.DEFAULT_CONTRACT_PATH).read_text(encoding="utf-8")
    )
    properties = schema["properties"]

    topology_schema = properties["topology"]["properties"]
    for stage in ("H-SYN", "P-SYN", "R-SYN"):
        assert topology_schema[stage]["additionalProperties"] is False
        for key, value in contract["topology"][stage].items():
            assert topology_schema[stage]["properties"][key]["const"] == value

    matrices_schema = properties["matrices"]["properties"]
    for matrix in ("final_closure_matrix", "thesis_claim_evidence_matrix"):
        assert matrices_schema[matrix]["properties"]["sort_key"]["const"] == (
            contract["matrices"][matrix]["sort_key"]
        )
    assert properties["outputs"]["properties"]["ordered_paths"]["const"] == (
        contract["outputs"]["ordered_paths"]
    )

    invariant_schema = properties["invariants"]
    for name in (
        "unavailable_is_not_negative_result",
        "confidence_intervals_precede_p_values",
        "descriptive_results_are_not_confirmatory",
    ):
        assert name in invariant_schema["required"]
        assert invariant_schema["properties"][name]["const"] is True

    adjudication_schema = properties["adjudication"]["properties"]
    for name in (
        "decisive_experiments",
        "registered_hypotheses",
        "verdict_vocabulary",
    ):
        assert adjudication_schema[name]["const"] == contract["adjudication"][name]


def test_real_allowlist_matches_every_source_commit_blob() -> None:
    contract = contract_module.load_contract(root=ROOT)
    records = contract_module.collect_input_records(contract, root=ROOT)

    assert len(records) == 83
    assert [record["path"] for record in records] == list(contract.allowed_input_paths)
    assert all(record["git_mode"] == "100644" for record in records)
    assert all(record["bytes"] >= 0 for record in records)
    assert all(len(record["sha256"]) == 64 for record in records)
    assert contract_module.digest_records(records) == contract_module.digest_records(records)


@pytest.mark.parametrize(
    "bad_path",
    [
        "private/FULL.md",
        "data/targets/monthly_targets_model_v0.parquet",
        "reports/closure_v1/**/*.csv",
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
    ],
)
def test_contract_rejects_forbidden_or_discovered_inputs(
    tmp_path: Path, bad_path: str
) -> None:
    real = contract_module.load_contract(root=ROOT)
    payload = copy.deepcopy(dict(real.raw))
    payload["allowed_inputs"] = list(payload["allowed_inputs"])
    payload["allowed_inputs"].append(
        {"path": bad_path, "role": "forbidden_probe", "format": "csv"}
    )
    payload["allowed_inputs"] = sorted(
        payload["allowed_inputs"], key=lambda item: item["path"]
    )

    with pytest.raises(contract_module.SynthesisContractError):
        contract_module.load_contract(
            root=ROOT,
            contract_path=_write_contract(tmp_path, payload),
        )


def test_contract_rejects_holm_family_reduction(tmp_path: Path) -> None:
    real = contract_module.load_contract(root=ROOT)
    payload = copy.deepcopy(dict(real.raw))
    payload["invariants"]["holm_universes"]["B"] = 13

    with pytest.raises(contract_module.SynthesisContractError, match="Holm"):
        contract_module.load_contract(
            root=ROOT,
            contract_path=_write_contract(tmp_path, payload),
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("availability", "Availability-state"),
        ("output_order", "output order"),
        ("caption", "caption"),
        ("topology", "topology"),
        ("registered_hypothesis", "Registered-hypothesis"),
    ],
)
def test_contract_rejects_static_control_drift(
    tmp_path: Path, mutation: str, match: str
) -> None:
    real = contract_module.load_contract(root=ROOT)
    payload = copy.deepcopy(dict(real.raw))
    if mutation == "availability":
        payload["invariants"]["availability_states"][0] = "missing"
    elif mutation == "output_order":
        payload["outputs"]["ordered_paths"][0:2] = reversed(
            payload["outputs"]["ordered_paths"][0:2]
        )
    elif mutation == "caption":
        del payload["captions"]["literal_by_artifact"]["F08"]
    elif mutation == "topology":
        payload["topology"]["ordered_stages"] = ["H-SYN", "R-SYN", "P-SYN"]
    else:
        payload["adjudication"]["registered_hypotheses"]["H1"][0] = (
            "H1_unregistered_probe"
        )

    with pytest.raises(contract_module.SynthesisContractError, match=match):
        contract_module.load_contract(
            root=ROOT,
            contract_path=_write_contract(tmp_path, payload),
        )


def test_regular_input_boundary_rejects_hardlinks_and_symlink_ancestors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    hardlink = tmp_path / "hardlink.csv"
    os.link(source, hardlink)
    with pytest.raises(contract_module.SynthesisContractError, match="single-link"):
        contract_module._regular_repo_file(tmp_path, "source.csv")

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    (real_parent / "input.csv").write_text("value\n1\n", encoding="utf-8")
    (tmp_path / "linked").symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(contract_module.SynthesisContractError, match="parent"):
        contract_module._regular_repo_file(tmp_path, "linked/input.csv")


def test_canonical_json_and_csv_are_stable_and_lf_only() -> None:
    json_payload = contract_module.canonical_json_bytes({"z": 1, "a": "snowman ☃"})
    assert json_payload == b'{"a":"snowman \xe2\x98\x83","z":1}\n'
    assert b"\r" not in json_payload

    csv_payload = contract_module.csv_bytes(
        [{"a": "1", "b": "not_estimable"}], ("a", "b")
    )
    assert csv_payload == b"a,b\n1,not_estimable\n"
    assert b"\r" not in csv_payload
