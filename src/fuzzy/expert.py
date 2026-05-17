"""Expert fuzzy layer for initial PIPE state construction.

This module implements the non-adaptive expert fuzzy fallback described in the
project document. It produces ecological pseudo-labels and the state vector
S(t), but it does not claim learned ANFIS adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


KEY_COLUMNS = ["source_id", "site_id", "site_id_source", "site_name", "year_month"]
STATE_COLUMNS = ["yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T", "delta_yN", "delta_yF", "delta_yT"]
EVIDENCE_COLUMNS = ["evidence_N", "evidence_F", "evidence_T"]
DEFAULT_IRC_WEIGHTS = {"alpha": 1.0, "beta": 1.0, "gamma": 1.0}


@dataclass(frozen=True)
class WeightedSignal:
    value: pd.Series
    missing_fraction: pd.Series

    @property
    def evidence(self) -> pd.Series:
        return (1.0 - self.missing_fraction).clip(0.0, 1.0)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def _clip01(values: pd.Series | np.ndarray) -> pd.Series:
    return pd.Series(np.clip(np.asarray(values, dtype="float64"), 0.0, 1.0))


def ramp_up(values: pd.Series, low: float, high: float) -> pd.Series:
    out = (values - low) / (high - low)
    return pd.Series(np.clip(out, 0.0, 1.0), index=values.index, dtype="float64").where(values.notna())


def ramp_down(values: pd.Series, low: float, high: float) -> pd.Series:
    out = 1.0 - (values - low) / (high - low)
    return pd.Series(np.clip(out, 0.0, 1.0), index=values.index, dtype="float64").where(values.notna())


def log_ramp_up(values: pd.Series, low: float, high: float, epsilon: float = 0.1) -> pd.Series:
    safe_values = values.where(values >= 0)
    log_values = np.log(safe_values + epsilon)
    return ramp_up(pd.Series(log_values, index=values.index), np.log(low + epsilon), np.log(high + epsilon))


def trapezoid(values: pd.Series, a: float, b: float, c: float, d: float) -> pd.Series:
    rising = ramp_up(values, a, b)
    falling = ramp_down(values, c, d)
    out = np.minimum(rising.fillna(0.0), falling.fillna(0.0))
    out = pd.Series(out, index=values.index, dtype="float64")
    out.loc[(values >= b) & (values <= c)] = 1.0
    return out.where(values.notna())


def triangle(values: pd.Series, a: float, b: float, c: float) -> pd.Series:
    rising = ramp_up(values, a, b)
    falling = ramp_down(values, b, c)
    out = np.minimum(rising.fillna(0.0), falling.fillna(0.0))
    out = pd.Series(out, index=values.index, dtype="float64")
    out.loc[values == b] = 1.0
    return out.where(values.notna())


def weighted_signal(signals: dict[str, pd.Series], weights: dict[str, float], fallback: float = 0.5) -> WeightedSignal:
    if not signals:
        raise ValueError("weighted_signal requires at least one signal")
    index = next(iter(signals.values())).index
    numerator = pd.Series(0.0, index=index, dtype="float64")
    denominator = pd.Series(0.0, index=index, dtype="float64")
    total_weight = float(sum(weights[name] for name in signals))
    for name, signal in signals.items():
        weight = float(weights[name])
        clean = signal.replace([np.inf, -np.inf], np.nan)
        mask = clean.notna()
        numerator.loc[mask] += clean.loc[mask] * weight
        denominator.loc[mask] += weight
    value = numerator / denominator.replace(0.0, np.nan)
    value = value.fillna(fallback).clip(0.0, 1.0)
    missing_fraction = (1.0 - denominator / total_weight).clip(0.0, 1.0)
    return WeightedSignal(value=value, missing_fraction=missing_fraction)


def weighted_qc_penalty(frame: pd.DataFrame, qc_columns: dict[str, str], weights: dict[str, float]) -> pd.Series:
    if not qc_columns:
        return pd.Series(0.5, index=frame.index, dtype="float64")
    numerator = pd.Series(0.0, index=frame.index, dtype="float64")
    denominator = pd.Series(0.0, index=frame.index, dtype="float64")
    for signal_name, column in qc_columns.items():
        if column not in frame.columns:
            continue
        qc = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).clip(0.0, 1.0)
        mask = qc.notna()
        weight = float(weights[signal_name])
        numerator.loc[mask] += qc.loc[mask] * weight
        denominator.loc[mask] += weight
    mean_qc = numerator / denominator.replace(0.0, np.nan)
    return (1.0 - mean_qc.fillna(0.5)).clip(0.0, 1.0)


def module_sigma(value: pd.Series, missing_fraction: pd.Series, qc_penalty: pd.Series) -> pd.Series:
    ambiguity = (1.0 - (value - 0.5).abs() * 2.0).clip(0.0, 1.0)
    sigma = 0.10 + 0.35 * missing_fraction + 0.25 * qc_penalty + 0.20 * ambiguity
    return sigma.clip(0.0, 1.0)


def label_from_score(
    score: pd.Series,
    *,
    low: str,
    medium: str,
    high: str,
    missing: str = "unknown",
) -> pd.Series:
    labels = pd.Series(missing, index=score.index, dtype="string")
    labels.loc[score < 0.33] = low
    labels.loc[(score >= 0.33) & (score < 0.66)] = medium
    labels.loc[score >= 0.66] = high
    return labels


def trophic_memberships(chla: pd.Series) -> pd.DataFrame:
    memberships = pd.DataFrame(index=chla.index)
    memberships["mu_trophic_oligotrophic"] = ramp_down(chla, 2.6, 7.3)
    memberships["mu_trophic_mesotrophic"] = triangle(chla, 2.6, 7.3, 20.0)
    memberships["mu_trophic_eutrophic"] = triangle(chla, 7.3, 30.0, 56.0)
    memberships["mu_trophic_hypereutrophic"] = ramp_up(chla, 56.0, 100.0)
    memberships = memberships.fillna(0.0).clip(0.0, 1.0)
    return memberships


def trophic_state_from_memberships(memberships: pd.DataFrame, chla: pd.Series) -> pd.Series:
    name_map = {
        "mu_trophic_oligotrophic": "oligotrophic",
        "mu_trophic_mesotrophic": "mesotrophic",
        "mu_trophic_eutrophic": "eutrophic",
        "mu_trophic_hypereutrophic": "hypereutrophic",
    }
    state = memberships.idxmax(axis=1).map(name_map).astype("string")
    state.loc[chla.isna()] = "unknown"
    return state


def nutrient_pressure(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    tp = _numeric(frame, "mean_TP_ugL")
    tn = _numeric(frame, "mean_TN_ugL")
    ratio = _numeric(frame, "TN_TP_ratio")
    tp_pressure = log_ramp_up(tp, 10.0, 100.0)
    tn_pressure = log_ramp_up(tn, 300.0, 1500.0)
    ratio_low_pressure = ramp_down(ratio, 8.0, 16.0)
    ratio_high_pressure = ramp_up(ratio, 50.0, 100.0)
    ratio_pressure = pd.concat([ratio_low_pressure, ratio_high_pressure], axis=1).max(axis=1).where(ratio.notna())
    components = {
        "tp_pressure": tp_pressure,
        "tn_pressure": tn_pressure,
        "ratio_imbalance_pressure": ratio_pressure,
    }
    weights = {"tp_pressure": 0.45, "tn_pressure": 0.35, "ratio_imbalance_pressure": 0.20}
    signal = weighted_signal(components, weights, fallback=0.5)
    qc_penalty = weighted_qc_penalty(
        frame,
        {
            "tp_pressure": "qc_ok_rate_TP_ugL",
            "tn_pressure": "qc_ok_rate_TN_ugL",
        },
        weights,
    )
    sigma = module_sigma(signal.value, signal.missing_fraction, qc_penalty)
    trace = pd.DataFrame(components).assign(
        yN=signal.value,
        sigma_N=sigma,
        evidence_N=signal.evidence,
        missing_N=signal.missing_fraction,
        qc_penalty_N=qc_penalty,
        nutrient_pressure_label=label_from_score(
            signal.value,
            low="low_nutrient_pressure",
            medium="moderate_nutrient_pressure",
            high="high_nutrient_pressure",
        ),
    )
    return signal.value, sigma, trace


def physicochemical_condition(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    dissolved_oxygen = _numeric(frame, "mean_DO_mgL")
    ph = _numeric(frame, "mean_pH")
    turbidity = _numeric(frame, "mean_turbidity_NTU")
    secchi = _numeric(frame, "mean_secchi_depth_m")
    do_good = trapezoid(dissolved_oxygen, 5.0, 7.0, 12.0, 15.0)
    ph_good = trapezoid(ph, 6.5, 7.0, 8.6, 9.5)
    turbidity_good = ramp_down(turbidity, 5.0, 50.0)
    secchi_good = ramp_up(secchi, 0.5, 3.0)
    components = {
        "do_good": do_good,
        "ph_good": ph_good,
        "turbidity_good": turbidity_good,
        "secchi_good": secchi_good,
    }
    weights = {"do_good": 0.30, "ph_good": 0.30, "turbidity_good": 0.20, "secchi_good": 0.20}
    signal = weighted_signal(components, weights, fallback=0.5)
    qc_penalty = weighted_qc_penalty(
        frame,
        {
            "do_good": "qc_ok_rate_DO_mgL",
            "ph_good": "qc_ok_rate_pH",
            "turbidity_good": "qc_ok_rate_turbidity_NTU",
            "secchi_good": "qc_ok_rate_secchi_depth_m",
        },
        weights,
    )
    sigma = module_sigma(signal.value, signal.missing_fraction, qc_penalty)
    trace = pd.DataFrame(components).assign(
        yF=signal.value,
        sigma_F=sigma,
        evidence_F=signal.evidence,
        missing_F=signal.missing_fraction,
        qc_penalty_F=qc_penalty,
        physicochemical_condition_label=label_from_score(
            signal.value,
            low="poor_physicochemical_condition",
            medium="intermediate_physicochemical_condition",
            high="good_physicochemical_condition",
        ),
    )
    return signal.value, sigma, trace


def thermal_biological_favorability(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    temperature = _numeric(frame, "mean_temperature_C")
    chla = _numeric(frame, "mean_chlorophyll_a_ugL")
    risk_chla = _numeric(frame, "risk_chla")
    chla_pressure = risk_chla.where(risk_chla.notna(), log_ramp_up(chla, 5.0, 30.0))
    temp_favorable = trapezoid(temperature, 15.0, 22.0, 30.0, 35.0)
    components = {
        "temp_favorable": temp_favorable,
        "current_chla_pressure": chla_pressure,
    }
    weights = {"temp_favorable": 0.45, "current_chla_pressure": 0.55}
    signal = weighted_signal(components, weights, fallback=0.5)
    qc_penalty = weighted_qc_penalty(
        frame,
        {
            "temp_favorable": "qc_ok_rate_temperature_C",
            "current_chla_pressure": "qc_ok_rate_chlorophyll_a_ugL",
        },
        weights,
    )
    sigma = module_sigma(signal.value, signal.missing_fraction, qc_penalty)
    no_chla_components = {"temp_favorable": temp_favorable}
    no_chla_weights = {"temp_favorable": 1.0}
    no_chla_signal = weighted_signal(no_chla_components, no_chla_weights, fallback=0.5)
    no_chla_qc_penalty = weighted_qc_penalty(
        frame,
        {"temp_favorable": "qc_ok_rate_temperature_C"},
        no_chla_weights,
    )
    no_chla_sigma = module_sigma(no_chla_signal.value, no_chla_signal.missing_fraction, no_chla_qc_penalty)
    trace = pd.DataFrame(components).assign(
        yT=signal.value,
        sigma_T=sigma,
        evidence_T=signal.evidence,
        missing_T=signal.missing_fraction,
        qc_penalty_T=qc_penalty,
        yT_no_chla=no_chla_signal.value,
        sigma_T_no_chla=no_chla_sigma,
        evidence_T_no_chla=no_chla_signal.evidence,
        missing_T_no_chla=no_chla_signal.missing_fraction,
        qc_penalty_T_no_chla=no_chla_qc_penalty,
        thermal_biological_label=label_from_score(
            signal.value,
            low="low_thermal_biological_favorability",
            medium="moderate_thermal_biological_favorability",
            high="high_thermal_biological_favorability",
        ),
    )
    return signal.value, sigma, no_chla_signal.value, no_chla_sigma, trace


def compute_irc1(
    y_n: pd.Series,
    y_f: pd.Series,
    y_t: pd.Series,
    weights: dict[str, float] | None = None,
) -> pd.Series:
    weights = weights or DEFAULT_IRC_WEIGHTS
    alpha = float(weights["alpha"])
    beta = float(weights["beta"])
    gamma = float(weights["gamma"])
    denominator = alpha + beta + gamma
    if denominator <= 0:
        raise ValueError("IRC weights must sum to a positive value")
    irc = (alpha * y_n + beta * (1.0 - y_f) + gamma * y_t) / denominator
    return irc.clip(0.0, 1.0)


def build_expert_state(
    panel: pd.DataFrame,
    *,
    irc_weights: dict[str, float] | None = None,
    include_trace_columns: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_keys = [column for column in KEY_COLUMNS if column not in panel.columns]
    if missing_keys:
        raise ValueError(f"Panel is missing required key columns: {missing_keys}")

    frame = panel.copy()
    y_n, sigma_n, trace_n = nutrient_pressure(frame)
    y_f, sigma_f, trace_f = physicochemical_condition(frame)
    y_t, sigma_t, y_t_no_chla, sigma_t_no_chla, trace_t = thermal_biological_favorability(frame)
    chla = _numeric(frame, "mean_chlorophyll_a_ugL")
    trophic = trophic_memberships(chla)
    state = frame[KEY_COLUMNS].copy()
    state["yN"] = y_n
    state["yF"] = y_f
    state["yT"] = y_t
    state["yT_no_chla"] = y_t_no_chla
    state["sigma_N"] = sigma_n
    state["sigma_F"] = sigma_f
    state["sigma_T"] = sigma_t
    state["sigma_T_no_chla"] = sigma_t_no_chla
    state["evidence_N"] = trace_n["evidence_N"]
    state["evidence_F"] = trace_f["evidence_F"]
    state["evidence_T"] = trace_t["evidence_T"]
    state["evidence_T_no_chla"] = trace_t["evidence_T_no_chla"]
    state["missing_N"] = trace_n["missing_N"]
    state["missing_F"] = trace_f["missing_F"]
    state["missing_T"] = trace_t["missing_T"]
    state["missing_T_no_chla"] = trace_t["missing_T_no_chla"]
    state["irc1"] = compute_irc1(y_n, y_f, y_t, irc_weights)
    state["irc1_no_chla"] = compute_irc1(y_n, y_f, y_t_no_chla, irc_weights)
    state["risk_chla_current"] = _numeric(frame, "risk_chla")
    state["chlorophyll_a_ugL_current"] = chla
    state["nutrient_pressure_label"] = trace_n["nutrient_pressure_label"]
    state["physicochemical_condition_label"] = trace_f["physicochemical_condition_label"]
    state["thermal_biological_label"] = trace_t["thermal_biological_label"]
    state["state_trophic_expert"] = trophic_state_from_memberships(trophic, chla)
    for column in trophic.columns:
        state[column] = trophic[column]

    sortable_month = pd.PeriodIndex(state["year_month"].astype(str), freq="M")
    state["_period_ordinal"] = sortable_month.astype("int64")
    state = state.sort_values(["source_id", "site_id", "_period_ordinal"]).reset_index(drop=True)
    grouped = state.groupby(["source_id", "site_id"], dropna=False)
    state["delta_yN"] = grouped["yN"].diff().fillna(0.0)
    state["delta_yF"] = grouped["yF"].diff().fillna(0.0)
    state["delta_yT"] = grouped["yT"].diff().fillna(0.0)
    state["delta_yT_no_chla"] = grouped["yT_no_chla"].diff().fillna(0.0)
    state = state.drop(columns=["_period_ordinal"])

    trace = pd.concat(
        [
            frame[KEY_COLUMNS].reset_index(drop=True),
            trace_n.reset_index(drop=True),
            trace_f.reset_index(drop=True),
            trace_t.reset_index(drop=True),
            trophic.reset_index(drop=True),
        ],
        axis=1,
    )
    trace["irc1"] = compute_irc1(trace["yN"], trace["yF"], trace["yT"], irc_weights)
    trace["irc1_no_chla"] = compute_irc1(trace["yN"], trace["yF"], trace["yT_no_chla"], irc_weights)
    if include_trace_columns:
        state = state.merge(trace, on=KEY_COLUMNS, how="left", suffixes=("", "_trace"))
    return state, trace


def rules_table(irc_weights: dict[str, float] | None = None) -> pd.DataFrame:
    weights = irc_weights or DEFAULT_IRC_WEIGHTS
    rows: list[dict[str, Any]] = [
        {
            "module": "ANFIS-N expert fallback",
            "rule_id": "N1",
            "inputs": "TP, TN, TN:TP",
            "rule": "Higher TP and TN increase nutrient pressure; extreme TN:TP imbalance adds pressure.",
            "output": "yN",
            "high_means": "high nutrient pressure",
            "weight_alpha_beta_gamma": weights["alpha"],
        },
        {
            "module": "ANFIS-F expert fallback",
            "rule_id": "F1",
            "inputs": "DO, pH, turbidity, Secchi",
            "rule": "Good DO, near-neutral pH, low turbidity, and high Secchi increase yF.",
            "output": "yF",
            "high_means": "good physicochemical condition",
            "weight_alpha_beta_gamma": weights["beta"],
        },
        {
            "module": "ANFIS-T expert fallback",
            "rule_id": "T1",
            "inputs": "temperature, current Chl-a",
            "rule": "Warm water and elevated current Chl-a increase thermal-biological favorability.",
            "output": "yT",
            "high_means": "high thermal-biological favorability",
            "weight_alpha_beta_gamma": weights["gamma"],
        },
        {
            "module": "ANFIS-T expert fallback",
            "rule_id": "T2",
            "inputs": "temperature",
            "rule": "Temperature-only variant excludes current Chl-a for exogenous ablation.",
            "output": "yT_no_chla",
            "high_means": "high thermal favorability without current Chl-a",
            "weight_alpha_beta_gamma": weights["gamma"],
        },
        {
            "module": "IRC1",
            "rule_id": "IRC1",
            "inputs": "yN, yF, yT",
            "rule": "IRC1 = (alpha*yN + beta*(1-yF) + gamma*yT)/(alpha+beta+gamma).",
            "output": "irc1",
            "high_means": "higher composite bloom risk",
            "weight_alpha_beta_gamma": f"{weights['alpha']},{weights['beta']},{weights['gamma']}",
        },
    ]
    return pd.DataFrame(rows)


def membership_spec_table() -> pd.DataFrame:
    rows = [
        ("tp_pressure", "log_ramp_up", "mean_TP_ugL", "low=10, high=100"),
        ("tn_pressure", "log_ramp_up", "mean_TN_ugL", "low=300, high=1500"),
        ("ratio_imbalance_pressure_low", "ramp_down", "TN_TP_ratio", "low=8, high=16"),
        ("ratio_imbalance_pressure_high", "ramp_up", "TN_TP_ratio", "low=50, high=100"),
        ("do_good", "trapezoid", "mean_DO_mgL", "a=5, b=7, c=12, d=15"),
        ("ph_good", "trapezoid", "mean_pH", "a=6.5, b=7, c=8.6, d=9.5"),
        ("turbidity_good", "ramp_down", "mean_turbidity_NTU", "low=5, high=50"),
        ("secchi_good", "ramp_up", "mean_secchi_depth_m", "low=0.5, high=3"),
        ("temp_favorable", "trapezoid", "mean_temperature_C", "a=15, b=22, c=30, d=35"),
        ("current_chla_pressure", "risk_chla/log_ramp_up", "risk_chla or mean_chlorophyll_a_ugL", "low=5, high=30"),
        ("temp_favorable_no_chla", "trapezoid", "mean_temperature_C", "a=15, b=22, c=30, d=35"),
        ("trophic_oligotrophic", "ramp_down", "mean_chlorophyll_a_ugL", "low=2.6, high=7.3"),
        ("trophic_mesotrophic", "triangle", "mean_chlorophyll_a_ugL", "a=2.6, b=7.3, c=20"),
        ("trophic_eutrophic", "triangle", "mean_chlorophyll_a_ugL", "a=7.3, b=30, c=56"),
        ("trophic_hypereutrophic", "ramp_up", "mean_chlorophyll_a_ugL", "low=56, high=100"),
    ]
    return pd.DataFrame(rows, columns=["membership", "function", "input_column", "parameters"])
