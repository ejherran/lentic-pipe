from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest
import yaml

from src.experiments.build_pipe_sequences import INPUT_COLUMNS, PIPE_STATE_COLUMNS, TARGET_COLUMNS
from src.experiments import evaluate_raw_degraded_pipe_grud_rollouts as raw_degradation
from src.experiments.evaluate_raw_degraded_pipe_grud_rollouts import raw_variable_group_columns
from src.experiments.train_pipe_grud import STATE_TARGET_NAMES, make_model


def _panel_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in range(1, 6):
        tp = 20.0 + month * 5.0
        tn = 500.0 + month * 80.0
        chla = 4.0 + month * 4.0
        rows.append(
            {
                "source_id": "A",
                "site_id": "s1",
                "site_id_source": "s1",
                "site_name": "Site 1",
                "year_month": f"2022-{month:02d}",
                "mean_TP_ugL": tp,
                "mean_TN_ugL": tn,
                "mean_chlorophyll_a_ugL": chla,
                "mean_temperature_C": 24.0,
                "qc_ok_rate_TP_ugL": 1.0,
                "qc_ok_rate_TN_ugL": 1.0,
                "qc_ok_rate_chlorophyll_a_ugL": 1.0,
                "qc_ok_rate_temperature_C": 1.0,
                "TN_TP_ratio": tn / tp,
                "log_TP": np.log(tp + 0.1),
                "log_TN": np.log(tn + 0.1),
                "log_chlorophyll_a": np.log(chla + 0.1),
                "risk_chla": min(max((np.log(chla + 0.1) - np.log(5.1)) / (np.log(30.1) - np.log(5.1)), 0.0), 1.0),
            }
        )
    rows.append(
        {
            "source_id": "B",
            "site_id": "survey_only",
            "site_id_source": "survey_only",
            "site_name": "Survey Only",
            "year_month": "2022-01",
            "mean_TP_ugL": 30.0,
            "mean_TN_ugL": 600.0,
            "mean_chlorophyll_a_ugL": 10.0,
            "mean_temperature_C": 24.0,
            "qc_ok_rate_TP_ugL": 1.0,
            "qc_ok_rate_TN_ugL": 1.0,
            "qc_ok_rate_chlorophyll_a_ugL": 1.0,
            "qc_ok_rate_temperature_C": 1.0,
            "TN_TP_ratio": 20.0,
            "log_TP": np.log(30.1),
            "log_TN": np.log(600.1),
            "log_chlorophyll_a": np.log(10.1),
            "risk_chla": 0.4,
        }
    )
    return pd.DataFrame(rows)


def _target_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for origin_month in ["2022-02", "2022-03"]:
        origin_period = cast(pd.Period, pd.Period(origin_month, freq="M"))
        for horizon in [1, 2]:
            rows.append(
                {
                    "source_id": "A",
                    "site_id": "s1",
                    "origin_year_month": origin_month,
                    "horizon_months": horizon,
                    "split": "test",
                    "target_year_month": str(origin_period + horizon),
                    "bloom_h": 1,
                    "target_risk_chla_h": 0.8,
                }
            )
    return pd.DataFrame(rows)


def _thresholds() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "policy_name": "closest_pr",
                "target_event": "irc_alert",
                "rollout_horizon_months": 1,
                "score_column": "alert_probability_irc",
                "selected_threshold": 0.5,
            },
            {
                "policy_name": "closest_pr",
                "target_event": "irc_alert",
                "rollout_horizon_months": 2,
                "score_column": "alert_probability_irc",
                "selected_threshold": 0.5,
            },
        ]
    )


def _write_identity_residual_model(path: Path, history_length: int = 2) -> None:
    torch = pytest.importorskip("torch")
    model = make_model(
        input_dim=len(INPUT_COLUMNS),
        target_dim=len(TARGET_COLUMNS),
        hidden_dim=4,
        num_layers=1,
        dropout=0.0,
        residual_mode="add_last",
    )
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    torch.save(
        {
            "model_version": "pipe_grud_v0",
            "best_epoch": 1,
            "best_validation_loss": 0.0,
            "best_validation_objective": 0.0,
            "config": {
                "history_length": history_length,
                "hidden_dim": 4,
                "num_layers": 1,
                "dropout": 0.0,
                "residual_mode": "add_last",
                "mse_weight": 0.0,
            },
            "input_columns": INPUT_COLUMNS,
            "target_columns": TARGET_COLUMNS,
            "target_weights": {},
            "output_blend_weights": {target: 1.0 for target in STATE_TARGET_NAMES},
            "model_state_dict": model.state_dict(),
        },
        path,
    )


def _config_text() -> str:
    return textwrap.dedent(
        """
        schema_version: 1
        protocol:
          default_alert_policy:
            selection_objective: closest_pr
          comparison_alert_policies: []
        evaluation:
          splits:
            - test
        canonical_variable_groups:
          nutrients:
            variables:
              - TP_ugL
              - TN_ugL
              - TN_TP_ratio
              - log_TP
              - log_TN
        scenario_sets:
          raw_test:
            - control_observed
            - ablate_nutrients
        scenarios:
          - scenario_id: control_observed
            family: control
            tier: core
            operations: []
          - scenario_id: ablate_nutrients
            family: feature_family_ablation
            tier: core
            operations:
              - type: set_variables_missing
                variable_group: nutrients
        """
    ).strip()


def test_raw_variable_group_columns_expand_panel_aggregates_and_derivatives() -> None:
    config = yaml.safe_load(_config_text())
    columns = raw_variable_group_columns(config, "nutrients", _panel_rows())

    assert "mean_TP_ugL" in columns
    assert "qc_ok_rate_TP_ugL" in columns
    assert "mean_TN_ugL" in columns
    assert "qc_ok_rate_TN_ugL" in columns
    assert "TN_TP_ratio" in columns
    assert "log_TP" in columns
    assert "log_TN" in columns


def test_recomputed_sequences_preserve_requested_input_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_expert_state(panel: pd.DataFrame, *, irc_weights: dict[str, float]) -> tuple[pd.DataFrame, dict]:
        return panel, {}

    def fake_filter_state_sources(state: pd.DataFrame, source_ids: list[str]) -> pd.DataFrame:
        captured["source_ids"] = source_ids
        return state

    def fake_build_sequence_candidates(state: pd.DataFrame, *, input_surface: str = "full") -> pd.DataFrame:
        captured["input_surface"] = input_surface
        return state

    def fake_filter_leakage_safe_sequences(
        candidates: pd.DataFrame,
        args: object,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return candidates, pd.DataFrame()

    monkeypatch.setattr(raw_degradation, "build_expert_state", fake_build_expert_state)
    monkeypatch.setattr(raw_degradation, "filter_state_sources", fake_filter_state_sources)
    monkeypatch.setattr(raw_degradation, "build_sequence_candidates", fake_build_sequence_candidates)
    monkeypatch.setattr(raw_degradation, "filter_leakage_safe_sequences", fake_filter_leakage_safe_sequences)

    raw_degradation.build_recomputed_sequences(
        pd.DataFrame({"source_id": ["wqp"]}),
        irc_weights={"alpha": 0.5, "beta": 0.5, "gamma": 2.0},
        sequence_args=argparse.Namespace(input_surface="no_current_chla", source_ids_normalized=["wqp"]),
    )

    assert captured["input_surface"] == "no_current_chla"
    assert captured["source_ids"] == ["wqp"]


def test_evaluate_raw_degraded_pipe_grud_rollouts_preserves_labels(tmp_path: Path) -> None:
    pytest.importorskip("torch")

    config_path = tmp_path / "degradation.yaml"
    panel_path = tmp_path / "panel.parquet"
    sequences_path = tmp_path / "sequences.parquet"
    splits_path = tmp_path / "splits.parquet"
    thresholds_path = tmp_path / "thresholds.csv"
    model_path = tmp_path / "model.pt"
    model_manifest_path = tmp_path / "model_manifest.json"
    fuzzy_manifest_path = tmp_path / "fuzzy_manifest.json"
    state_metrics_path = tmp_path / "state_metrics.csv"
    alert_metrics_path = tmp_path / "alert_metrics.csv"
    policy_metrics_path = tmp_path / "policy_metrics.csv"
    summary_path = tmp_path / "summary.csv"
    examples_path = tmp_path / "examples.csv"
    diagnostics_path = tmp_path / "diagnostics.csv"
    backtest_rows_path = tmp_path / "backtest_rows.parquet"
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    config_path.write_text(_config_text(), encoding="utf-8")
    panel = _panel_rows()
    panel.to_parquet(panel_path, index=False)

    from src.experiments.evaluate_raw_degraded_pipe_grud_rollouts import build_recomputed_sequences

    sequences, _, _ = build_recomputed_sequences(
        panel,
        irc_weights={"alpha": 0.5, "beta": 0.5, "gamma": 2.0},
        sequence_args=argparse.Namespace(
            max_gap_months=1,
            train_end="2018-12",
            validation_start="2019-01",
            validation_end="2021-12",
            test_start="2022-01",
            test_end=None,
        ),
    )
    sequences.to_parquet(sequences_path, index=False)
    _target_rows().to_parquet(splits_path, index=False)
    _thresholds().to_csv(thresholds_path, index=False)
    _write_identity_residual_model(model_path)
    model_manifest_path.write_text('{"status": "test"}\n', encoding="utf-8")
    fuzzy_manifest_path.write_text(
        json.dumps({"irc_weights": {"alpha": 0.5, "beta": 0.5, "gamma": 2.0}}) + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "src/experiments/evaluate_raw_degraded_pipe_grud_rollouts.py",
            "--config",
            str(config_path),
            "--panel",
            str(panel_path),
            "--sequences",
            str(sequences_path),
            "--splits",
            str(splits_path),
            "--thresholds",
            str(thresholds_path),
            "--model",
            str(model_path),
            "--model-manifest",
            str(model_manifest_path),
            "--fuzzy-manifest",
            str(fuzzy_manifest_path),
            "--fuzzy-calibrators-dir",
            str(tmp_path / "missing_calibrators"),
            "--rollout-calibrator-dir",
            str(tmp_path / "missing_rollout_calibrators"),
            "--state-metrics",
            str(state_metrics_path),
            "--alert-metrics",
            str(alert_metrics_path),
            "--policy-metrics",
            str(policy_metrics_path),
            "--summary",
            str(summary_path),
            "--examples",
            str(examples_path),
            "--diagnostics",
            str(diagnostics_path),
            "--backtest-rows",
            str(backtest_rows_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--scenario-set",
            "raw_test",
            "--rollout-horizon",
            "2",
            "--deterministic",
            "--disable-calibrated-bloom",
            "--batch-size",
            "1",
            "--irc-alert-threshold",
            "0.5",
            "--alert-prob-threshold",
            "0.5",
        ],
        check=True,
    )

    summary = pd.read_csv(summary_path)
    policy_metrics = pd.read_csv(policy_metrics_path)
    diagnostics = pd.read_csv(diagnostics_path)
    backtest_rows = pd.read_parquet(backtest_rows_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert summary["scenario_id"].tolist() == ["control_observed", "ablate_nutrients"]
    assert summary["score_recomputed"].tolist() == [True, True]
    assert summary["labels_preserved"].tolist() == [True, True]
    degraded_summary = summary[summary["scenario_id"] == "ablate_nutrients"].iloc[0]
    assert bool(degraded_summary["fuzzy_state_rebuilt"])
    assert int(degraded_summary["raw_affected_cells"]) > 0
    assert int(degraded_summary["affected_sequence_cells"]) > 0
    assert set(policy_metrics["scenario_id"]) == {"control_observed", "ablate_nutrients"}
    assert "surface_by_source" in set(diagnostics["diagnostic_type"])
    assert "control_rebuild" in set(diagnostics["diagnostic_type"])
    assert "input_change" in set(diagnostics["diagnostic_type"])
    surface_b = diagnostics[
        (diagnostics["diagnostic_type"] == "surface_by_source") & (diagnostics["source_id"] == "B")
    ].iloc[0]
    assert int(surface_b["panel_rows"]) == 1
    assert int(surface_b["canonical_sequence_rows"]) == 0
    control_rebuild = diagnostics[diagnostics["diagnostic_type"] == "control_rebuild"].iloc[0]
    assert int(control_rebuild["alignment_missing_rows"]) == 0

    key = [
        "source_id",
        "site_id",
        "split",
        "origin_year_month",
        "forecast_year_month",
        "rollout_horizon_months",
    ]
    actuals = backtest_rows.pivot_table(index=key, columns="scenario_id", values="actual_irc", aggfunc="first")
    assert (actuals["control_observed"] == actuals["ablate_nutrients"]).all()
    assert manifest["status"] == "completed"
    assert manifest["config"]["fuzzy_weight_source"] == "fuzzy_manifest"
    assert manifest["row_counts"]["diagnostic_rows"] == len(diagnostics)
    assert "Raw-Predictor Recomputed" in report_path.read_text(encoding="utf-8")
