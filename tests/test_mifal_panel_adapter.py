from __future__ import annotations

import pandas as pd

from src.mifal.panel_adapter import (
    MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA,
    MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA,
    add_previous_chla_columns,
    panel_row_to_mifal_payload,
)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "a",
                "year_month": "2020-01",
                "mean_temperature_C": 22.0,
                "mean_TP_ugL": 50.0,
                "mean_TN_ugL": 800.0,
                "mean_secchi_depth_m": 1.1,
                "mean_turbidity_NTU": 12.0,
                "mean_DO_mgL": 7.0,
                "mean_chlorophyll_a_ugL": 12.0,
                "n_obs_temperature_C": 4,
                "n_obs_TP_ugL": 2,
                "n_obs_TN_ugL": 2,
                "n_obs_secchi_depth_m": 1,
                "n_obs_turbidity_NTU": 1,
                "n_obs_DO_mgL": 3,
                "n_obs_chlorophyll_a_ugL": 2,
                "qc_ok_rate_temperature_C": 1.0,
                "qc_ok_rate_TP_ugL": 0.9,
                "qc_ok_rate_TN_ugL": 0.9,
                "qc_ok_rate_secchi_depth_m": 1.0,
                "qc_ok_rate_turbidity_NTU": 1.0,
                "qc_ok_rate_DO_mgL": 0.8,
                "qc_ok_rate_chlorophyll_a_ugL": 1.0,
                "std_temperature_C": 0.5,
                "std_TP_ugL": 4.0,
                "std_TN_ugL": 100.0,
                "std_secchi_depth_m": 0.2,
                "std_turbidity_NTU": 3.0,
                "std_DO_mgL": 0.4,
                "std_chlorophyll_a_ugL": 2.0,
            },
            {
                "source_id": "wqp",
                "site_id": "a",
                "year_month": "2020-02",
                "mean_temperature_C": 24.0,
                "mean_TP_ugL": 70.0,
                "mean_TN_ugL": 900.0,
                "mean_secchi_depth_m": 0.8,
                "mean_turbidity_NTU": 20.0,
                "mean_DO_mgL": 5.5,
                "mean_chlorophyll_a_ugL": 35.0,
                "n_obs_temperature_C": 4,
                "n_obs_TP_ugL": 2,
                "n_obs_TN_ugL": 2,
                "n_obs_secchi_depth_m": 1,
                "n_obs_turbidity_NTU": 1,
                "n_obs_DO_mgL": 3,
                "n_obs_chlorophyll_a_ugL": 2,
                "qc_ok_rate_temperature_C": 1.0,
                "qc_ok_rate_TP_ugL": 0.9,
                "qc_ok_rate_TN_ugL": 0.9,
                "qc_ok_rate_secchi_depth_m": 1.0,
                "qc_ok_rate_turbidity_NTU": 1.0,
                "qc_ok_rate_DO_mgL": 0.8,
                "qc_ok_rate_chlorophyll_a_ugL": 1.0,
                "std_temperature_C": 0.5,
                "std_TP_ugL": 4.0,
                "std_TN_ugL": 100.0,
                "std_secchi_depth_m": 0.2,
                "std_turbidity_NTU": 3.0,
                "std_DO_mgL": 0.4,
                "std_chlorophyll_a_ugL": 2.0,
            },
        ]
    )


def test_panel_adapter_uses_previous_month_chla_and_unit_transform() -> None:
    frame = add_previous_chla_columns(_panel())
    row = frame[frame["origin_year_month"] == "2020-02"].iloc[0].to_dict()

    payload = panel_row_to_mifal_payload(row, surface=MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA)

    assert payload["TN"].value == 0.9
    assert payload["Chl"].value == 35.0
    assert payload["Chl_prev"].value == 12.0
    assert payload["DOb"].source_fit == 0.55
    assert payload["Chl_prev"].age_days > payload["Chl"].age_days


def test_no_current_chla_surface_excludes_analysis_chla_but_keeps_lag() -> None:
    frame = add_previous_chla_columns(_panel())
    row = frame[frame["origin_year_month"] == "2020-02"].iloc[0].to_dict()

    payload = panel_row_to_mifal_payload(row, surface=MIFAL_SURFACE_OBSERVABLE_NO_CURRENT_CHLA)

    assert "Chl" not in payload
    assert payload["Chl_prev"].value == 12.0
    assert {"Tw", "TP", "TN", "Secchi", "Turb", "DOb", "Chl_prev"}.issubset(payload)


def test_panel_adapter_drops_values_outside_mifal_physical_bounds() -> None:
    frame = add_previous_chla_columns(_panel())
    row = frame[frame["origin_year_month"] == "2020-02"].iloc[0].to_dict()
    row["mean_temperature_C"] = -3.888888888888889

    payload = panel_row_to_mifal_payload(row, surface=MIFAL_SURFACE_OBSERVABLE_CURRENT_CHLA)

    assert "Tw" not in payload
    assert "TP" in payload
