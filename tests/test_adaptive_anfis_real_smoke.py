from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.fuzzy.expert import build_expert_state


def _panel() -> pd.DataFrame:
    rows = []
    for index in range(18):
        pressure = index / 17
        year = 2020 + index // 12
        month = 1 + index % 12
        source_id = "unit"
        site_id = f"S{index % 3}"
        rows.append(
            {
                "source_id": source_id,
                "site_id": site_id,
                "site_id_source": site_id,
                "site_name": f"Lake {site_id}",
                "year_month": f"{year}-{month:02d}",
                "mean_TP_ugL": 8.0 + 160.0 * pressure,
                "mean_TN_ugL": 250.0 + 2_200.0 * pressure,
                "TN_TP_ratio": 12.0 + 70.0 * pressure,
                "mean_DO_mgL": 10.0 - 7.0 * pressure,
                "mean_pH": 7.3 + 1.8 * pressure,
                "mean_turbidity_NTU": 2.0 + 75.0 * pressure,
                "mean_secchi_depth_m": 4.0 - 3.4 * pressure,
                "mean_temperature_C": 10.0 + 20.0 * pressure,
                "mean_chlorophyll_a_ugL": 1.0 + 60.0 * pressure,
                "risk_chla": pressure,
            }
        )
    frame = pd.DataFrame(rows)
    for variable in [
        "TP_ugL",
        "TN_ugL",
        "DO_mgL",
        "pH",
        "turbidity_NTU",
        "secchi_depth_m",
        "temperature_C",
        "chlorophyll_a_ugL",
    ]:
        frame[f"qc_ok_rate_{variable}"] = 1.0
    return frame


def _splits(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    split_by_index = ["train"] * 10 + ["validation"] * 4 + ["test"] * 4
    for index, (_, row) in enumerate(panel.reset_index(drop=True).iterrows()):
        risk = float(row["risk_chla"])
        rows.append(
            {
                "source_id": row["source_id"],
                "site_id": row["site_id"],
                "origin_year_month": row["year_month"],
                "horizon_months": 1,
                "split": split_by_index[index],
                "bloom_h": risk >= 0.55,
                "target_risk_chla_h": risk,
            }
        )
    return pd.DataFrame(rows)


def test_adaptive_anfis_real_smoke_cli_writes_bounded_outputs(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    panel = _panel()
    state, _ = build_expert_state(panel)
    panel_path = tmp_path / "panel.parquet"
    state_path = tmp_path / "state.parquet"
    splits_path = tmp_path / "splits.parquet"
    report_path = tmp_path / "real_smoke_report.md"
    manifest_path = tmp_path / "real_smoke_manifest.json"
    module_metrics_path = tmp_path / "real_smoke_module_metrics.csv"
    target_metrics_path = tmp_path / "real_smoke_target_metrics.csv"
    predictions_path = tmp_path / "real_smoke_predictions.csv"
    memberships_initial_path = tmp_path / "real_smoke_memberships_initial.csv"
    memberships_final_path = tmp_path / "real_smoke_memberships_final.csv"
    panel.to_parquet(panel_path, index=False)
    state.to_parquet(state_path, index=False)
    _splits(panel).to_parquet(splits_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/run_adaptive_anfis_real_smoke.py",
            "--panel",
            str(panel_path),
            "--state",
            str(state_path),
            "--splits",
            str(splits_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--module-metrics",
            str(module_metrics_path),
            "--target-metrics",
            str(target_metrics_path),
            "--predictions",
            str(predictions_path),
            "--memberships-initial",
            str(memberships_initial_path),
            "--memberships-final",
            str(memberships_final_path),
            "--horizons",
            "1",
            "--sample-rows-per-split-horizon",
            "10",
            "--train-rows-per-module",
            "10",
            "--min-module-rows",
            "3",
            "--epochs",
            "12",
            "--learning-rate",
            "0.04",
            "--min-output-std",
            "0.0",
        ],
        check=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    module_metrics = pd.read_csv(module_metrics_path)
    target_metrics = pd.read_csv(target_metrics_path)
    predictions = pd.read_csv(predictions_path)
    report = report_path.read_text(encoding="utf-8")

    assert manifest["status"] == "completed"
    assert manifest["sample_alignment"]["state_missing_rows"] == 0
    assert manifest["sample_alignment"]["panel_missing_rows"] == 0
    assert set(module_metrics["module"]) == {"ANFIS-N", "ANFIS-F", "ANFIS-T", "ANFIS-T-no-current"}
    assert set(module_metrics["status"]) == {"passed"}
    assert {"irc1_adaptive", "irc1_no_chla_adaptive"}.issubset(target_metrics["score_name"].unique())
    assert {"yT_adaptive", "yT_no_chla_adaptive"}.issubset(predictions.columns)
    assert "Status: `completed`" in report


def test_build_adaptive_anfis_state_cli_exports_state_and_checkpoints(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    panel = _panel()
    state, _ = build_expert_state(panel)
    panel_path = tmp_path / "panel.parquet"
    state_path = tmp_path / "state.parquet"
    splits_path = tmp_path / "splits.parquet"
    output_state_path = tmp_path / "adaptive_state.parquet"
    models_dir = tmp_path / "models"
    report_path = tmp_path / "adaptive_state_report.md"
    manifest_path = tmp_path / "adaptive_state_manifest.json"
    module_metrics_path = tmp_path / "adaptive_state_module_metrics.csv"
    target_metrics_path = tmp_path / "adaptive_state_target_metrics.csv"
    coverage_path = tmp_path / "adaptive_state_coverage.csv"
    memberships_initial_path = tmp_path / "adaptive_memberships_initial.csv"
    memberships_final_path = tmp_path / "adaptive_memberships_final.csv"
    panel.to_parquet(panel_path, index=False)
    state.to_parquet(state_path, index=False)
    _splits(panel).to_parquet(splits_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "src/experiments/build_adaptive_anfis_state.py",
            "--panel",
            str(panel_path),
            "--state",
            str(state_path),
            "--splits",
            str(splits_path),
            "--output-state",
            str(output_state_path),
            "--models-dir",
            str(models_dir),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--module-metrics",
            str(module_metrics_path),
            "--target-metrics",
            str(target_metrics_path),
            "--coverage",
            str(coverage_path),
            "--memberships-initial",
            str(memberships_initial_path),
            "--memberships-final",
            str(memberships_final_path),
            "--source-ids",
            "unit",
            "--horizons",
            "1",
            "--train-rows-per-module",
            "10",
            "--max-export-rows",
            "18",
            "--max-train-missing-fraction",
            "1.0",
            "--min-module-rows",
            "3",
            "--epochs",
            "12",
            "--learning-rate",
            "0.04",
            "--predict-batch-rows",
            "6",
            "--center-constraint",
            "unit",
            "--min-output-std",
            "0.0",
        ],
        check=True,
    )

    adaptive_state = pd.read_parquet(output_state_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    module_metrics = pd.read_csv(module_metrics_path)
    target_metrics = pd.read_csv(target_metrics_path)
    memberships_final = pd.read_csv(memberships_final_path)
    report = report_path.read_text(encoding="utf-8")

    assert manifest["status"] == "completed"
    assert manifest["config"]["center_constraint"] == "unit"
    assert manifest["alignment"]["export_rows"] == 18
    assert {"yN_adaptive", "sigma_N_adaptive", "delta_yT_no_chla_adaptive"}.issubset(adaptive_state.columns)
    assert adaptive_state["irc1_adaptive"].between(0.0, 1.0).all()
    assert set(module_metrics["module"]) == {"ANFIS-N", "ANFIS-F", "ANFIS-T", "ANFIS-T-no-current"}
    assert {"irc1_adaptive", "irc1_no_chla_adaptive"}.issubset(target_metrics["score_name"].unique())
    assert memberships_final["center"].between(0.0, 1.0).all()
    assert len(list(models_dir.glob("*.pt"))) == 4
    assert "Status: `completed`" in report
