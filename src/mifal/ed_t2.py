"""MIFAL-ED/T2 interval type-2 eco-fuzzy reference model.

The implementation is intentionally dependency-light and deterministic. The
default parameters are ecological priors, not fitted lake-specific constants;
they must be audited and calibrated before making empirical claims.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from math import exp, isfinite, log, sqrt
from typing import Any, TypeAlias, cast

__version__ = "5.0.0"

Number: TypeAlias = int | float
Interval: TypeAlias = tuple[float, float]


def clip01(x: float) -> float:
    value = float(x)
    if not isfinite(value):
        return 0.0
    return min(max(value, 0.0), 1.0)


def interval_clip01(x: Interval) -> Interval:
    lo, hi = clip01(x[0]), clip01(x[1])
    return (min(lo, hi), max(lo, hi))


def interval_not(x: Interval) -> Interval:
    lo, hi = interval_clip01(x)
    return interval_clip01((1.0 - hi, 1.0 - lo))


def interval_scale(x: Interval, factor: float) -> Interval:
    scale = max(0.0, float(factor))
    return interval_clip01((scale * x[0], scale * x[1]))


def safe_log(x: float, eps: float = 1e-12) -> float:
    value = float(x)
    if not isfinite(value):
        value = eps
    return log(max(value, eps))


def conservative_risk(interval: Interval, alpha: float = 0.65) -> float:
    weight = clip01(alpha)
    lo, hi = interval_clip01(interval)
    return clip01((1.0 - weight) * 0.5 * (lo + hi) + weight * hi)


def logistic_factor_interval(b: Interval) -> Interval:
    """Exact interval for q(B) = B(1 - B), B in [0, 1]."""

    lo, hi = interval_clip01(b)
    vals = [lo * (1.0 - lo), hi * (1.0 - hi)]
    q_min = min(vals)
    q_max = 0.25 if lo <= 0.5 <= hi else max(vals)
    return (q_min, q_max)


@dataclass(frozen=True)
class Observation:
    """Observation from one evidence source."""

    value: float
    source_quality: float = 1.0
    source_fit: float = 1.0
    sigma: float | None = None
    cv: float | None = None
    age_days: float = 0.0
    independence: float = 1.0


ObservationLike: TypeAlias = Number | Observation | Mapping[str, Number]
RawInput: TypeAlias = ObservationLike | Sequence[ObservationLike]


@dataclass(frozen=True)
class FusedValue:
    value: float
    sigma: float
    reliability: float
    available: bool
    age_days: float = 0.0
    n_sources: int = 0


def as_observations(raw: object | None) -> list[Observation]:
    if raw is None:
        return []
    if isinstance(raw, Observation):
        return [raw]
    if isinstance(raw, (int, float)):
        return [Observation(value=float(raw))]
    if isinstance(raw, Mapping):
        mapping = cast(Mapping[str, Any], raw)
        if mapping.get("value") is None:
            return []
        return [
            Observation(
                value=float(mapping["value"]),
                source_quality=float(mapping.get("source_quality", mapping.get("quality", 1.0))),
                source_fit=float(mapping.get("source_fit", mapping.get("fit", 1.0))),
                sigma=None if mapping.get("sigma") is None else float(mapping["sigma"]),
                cv=None if mapping.get("cv") is None else float(mapping["cv"]),
                age_days=float(mapping.get("age_days", mapping.get("age", 0.0))),
                independence=float(mapping.get("independence", mapping.get("independent", 1.0))),
            )
        ]
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        out: list[Observation] = []
        for item in raw:
            out.extend(as_observations(item))
        return out
    raise TypeError(f"Unsupported raw input type: {type(raw)!r}")


@dataclass(frozen=True)
class MembershipFunction:
    """Type-1 membership function used as an interval type-2 generator."""

    kind: str
    params: tuple[float, ...]

    def validate(self) -> None:
        kind = self.kind.lower()
        if kind == "trap":
            if len(self.params) != 4:
                raise ValueError("trap membership requires four parameters")
            a, b, c, d = self.params
            if not (a <= b <= c <= d):
                raise ValueError("trap parameters must satisfy a <= b <= c <= d")
        elif kind == "tri":
            if len(self.params) != 3:
                raise ValueError("tri membership requires three parameters")
            a, b, c = self.params
            if not (a <= b <= c):
                raise ValueError("tri parameters must satisfy a <= b <= c")
        elif kind == "gauss":
            if len(self.params) != 2 or abs(self.params[1]) <= 0:
                raise ValueError("gauss membership requires center and positive sigma")
        elif kind == "sigmoid":
            if len(self.params) != 2:
                raise ValueError("sigmoid membership requires center and slope")
        elif kind in {"ramp_up", "ramp_down"}:
            if len(self.params) != 2:
                raise ValueError(f"{kind} membership requires two parameters")
            a, b = self.params
            if not (a < b):
                raise ValueError(f"{kind} parameters must satisfy a < b")
        else:
            raise ValueError(f"Unknown membership function: {self.kind}")

    def __call__(self, x: float) -> float:
        kind = self.kind.lower()
        value = float(x)
        if kind == "trap":
            a, b, c, d = self.params
            if value < a or value > d:
                return 0.0
            if b <= value <= c:
                return 1.0
            if a <= value < b:
                return 1.0 if b == a else clip01((value - a) / max(b - a, 1e-12))
            if c < value <= d:
                return 1.0 if d == c else clip01((d - value) / max(d - c, 1e-12))
            return 0.0
        if kind == "tri":
            a, b, c = self.params
            if value < a or value > c:
                return 0.0
            if value == b:
                return 1.0
            if a <= value < b:
                return 1.0 if b == a else clip01((value - a) / max(b - a, 1e-12))
            if b < value <= c:
                return 1.0 if c == b else clip01((c - value) / max(c - b, 1e-12))
            return 0.0
        if kind == "gauss":
            center, sigma = self.params
            sigma = max(abs(sigma), 1e-12)
            return clip01(exp(-((value - center) ** 2) / (2.0 * sigma**2)))
        if kind == "sigmoid":
            center, slope = self.params
            z = slope * (value - center)
            if z >= 60.0:
                return 1.0
            if z <= -60.0:
                return 0.0
            return clip01(1.0 / (1.0 + exp(-z)))
        if kind == "ramp_up":
            a, b = self.params
            if value <= a:
                return 0.0
            if value >= b:
                return 1.0
            return clip01((value - a) / max(b - a, 1e-12))
        if kind == "ramp_down":
            a, b = self.params
            if value <= a:
                return 1.0
            if value >= b:
                return 0.0
            return clip01((b - value) / max(b - a, 1e-12))
        raise ValueError(f"Unknown membership function: {self.kind}")

    def _candidate_points(self, lo: float, hi: float, value: float, grid: int) -> list[float]:
        points = [lo, hi, value]
        points.extend(float(point) for point in self.params if lo <= point <= hi)
        if self.kind.lower() == "gauss":
            center = self.params[0]
            if lo <= center <= hi:
                points.append(float(center))
        grid = max(2, int(grid))
        points.extend(lo + (hi - lo) * index / (grid - 1) for index in range(grid))
        return points

    def interval(self, value: float, uncertainty: float, reliability: float, grid: int = 31) -> Interval:
        rho = clip01(reliability)
        radius = max(0.0, float(uncertainty))
        lo = float(value) - radius
        hi = float(value) + radius
        vals = [self(point) for point in self._candidate_points(lo, hi, float(value), grid)]
        return interval_clip01((rho * min(vals), max(vals)))


@dataclass
class MIFALConfig:
    """Model configuration and ecological priors.

    Default units: water temperature in deg C, TP in ug/L, TN in mg/L, Secchi
    in m, wind in m/s, residence time in days, flushing in day^-1, bottom DO in
    mg/L, and chlorophyll-a in ug/L.
    """

    alpha_precaution: float = 0.65
    tau_c_days: float = 7.0
    tau_memory_days: float = 10.0
    gamma0: float = 0.04
    gammaG: float = 0.65
    gammaM: float = 0.28
    delta0: float = 0.08
    deltaD: float = 0.55
    eta: float = 0.22
    lambda_N: float = 0.35
    lambda_P: float = 0.45
    lambda_R: float = 0.40
    lambda_L: float = 0.45
    lambda_H: float = 0.40
    lambda_D: float = 0.35
    lambda_M: float = 0.35
    lambda_G: float = 0.55
    initial_state: Interval = (0.05, 0.35)
    chl_base: float = 2.0
    chl_alert: float = 30.0
    allow_unknown_variables: bool = False
    strict_physical_bounds: bool = True
    variable_bounds: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "Tw": (0.0, 45.0),
            "TP": (0.0, 2000.0),
            "TN": (0.0, 100.0),
            "Secchi": (0.0, 50.0),
            "Turb": (0.0, 10000.0),
            "Wind": (0.0, 80.0),
            "Residence": (0.0, 10000.0),
            "Flushing": (0.0, 100.0),
            "Strat": (0.0, 1.0),
            "DOb": (0.0, 30.0),
            "Chl": (0.0, 10000.0),
            "Chl_prev": (0.0, 10000.0),
            "Phyco": (0.0, 1000.0),
            "Sat": (0.0, 1.0),
            "Visual": (0.0, 1.0),
            "Rain": (0.0, 1000.0),
            "LandLoad": (0.0, 1.0),
        }
    )
    tau_var: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 3.0,
            "TP": 25.0,
            "TN": 25.0,
            "Secchi": 10.0,
            "Turb": 7.0,
            "Wind": 1.0,
            "Residence": 30.0,
            "Flushing": 7.0,
            "Strat": 3.0,
            "DOb": 3.0,
            "Chl": 5.0,
            "Chl_prev": 7.0,
            "Phyco": 5.0,
            "Sat": 5.0,
            "Visual": 2.0,
            "Rain": 2.0,
            "LandLoad": 180.0,
        }
    )
    priors: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 24.0,
            "TP": 45.0,
            "TN": 0.8,
            "Secchi": 1.2,
            "Turb": 15.0,
            "Wind": 3.0,
            "Residence": 20.0,
            "Flushing": 0.05,
            "Strat": 0.4,
            "DOb": 5.0,
            "Chl": 8.0,
            "Chl_prev": 8.0,
            "Phyco": 0.2,
            "Sat": 0.2,
            "Visual": 0.0,
            "Rain": 5.0,
            "LandLoad": 0.4,
        }
    )
    default_sigma: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 1.0,
            "TP": 12.0,
            "TN": 0.25,
            "Secchi": 0.25,
            "Turb": 5.0,
            "Wind": 0.8,
            "Residence": 8.0,
            "Flushing": 0.02,
            "Strat": 0.15,
            "DOb": 0.8,
            "Chl": 3.0,
            "Chl_prev": 3.0,
            "Phyco": 0.1,
            "Sat": 0.1,
            "Visual": 0.25,
            "Rain": 5.0,
            "LandLoad": 0.25,
        }
    )
    uncertainty_floor: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 7.0,
            "TP": 70.0,
            "TN": 1.0,
            "Secchi": 1.5,
            "Turb": 40.0,
            "Wind": 4.0,
            "Residence": 40.0,
            "Flushing": 0.12,
            "Strat": 0.45,
            "DOb": 4.0,
            "Chl": 18.0,
            "Chl_prev": 18.0,
            "Phyco": 0.5,
            "Sat": 0.5,
            "Visual": 0.7,
            "Rain": 20.0,
            "LandLoad": 0.7,
        }
    )
    missing_bonus: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 2.0,
            "TP": 20.0,
            "TN": 0.4,
            "Secchi": 0.5,
            "Turb": 10.0,
            "Wind": 1.0,
            "Residence": 10.0,
            "Flushing": 0.03,
            "Strat": 0.15,
            "DOb": 1.0,
            "Chl": 6.0,
            "Chl_prev": 6.0,
            "Phyco": 0.15,
            "Sat": 0.15,
            "Visual": 0.20,
            "Rain": 5.0,
            "LandLoad": 0.2,
        }
    )
    sample_cost: dict[str, float] = field(
        default_factory=lambda: {
            "Tw": 0.2,
            "Wind": 0.2,
            "Secchi": 0.3,
            "Visual": 0.1,
            "Sat": 0.4,
            "Turb": 0.5,
            "DOb": 0.6,
            "Strat": 0.7,
            "Chl": 0.8,
            "Chl_prev": 0.8,
            "Phyco": 0.8,
            "TP": 1.0,
            "TN": 1.0,
            "Residence": 1.0,
            "Flushing": 1.0,
            "Rain": 0.1,
            "LandLoad": 1.0,
        }
    )
    membership: dict[str, dict[str, MembershipFunction]] = field(
        default_factory=lambda: {
            "Tw": {
                "favorable": MembershipFunction("gauss", (27.0, 6.0)),
                "high": MembershipFunction("ramp_up", (24.0, 30.0)),
            },
            "TP": {
                "medium": MembershipFunction("trap", (18.0, 32.0, 60.0, 95.0)),
                "high": MembershipFunction("ramp_up", (55.0, 85.0)),
            },
            "TN": {"sufficient": MembershipFunction("ramp_up", (0.35, 0.70))},
            "Secchi": {"adequate": MembershipFunction("ramp_up", (0.25, 0.70))},
            "Turb": {"high": MembershipFunction("ramp_up", (25.0, 50.0))},
            "Wind": {
                "low": MembershipFunction("ramp_down", (2.0, 4.0)),
                "high": MembershipFunction("ramp_up", (4.0, 6.5)),
            },
            "Residence": {"high": MembershipFunction("ramp_up", (12.0, 25.0))},
            "Flushing": {"high": MembershipFunction("ramp_up", (0.06, 0.12))},
            "Strat": {"high": MembershipFunction("ramp_up", (0.30, 0.60))},
            "DOb": {"low": MembershipFunction("ramp_down", (2.0, 4.0))},
            "Chl": {"high": MembershipFunction("ramp_up", (15.0, 30.0))},
            "Chl_prev": {"high": MembershipFunction("ramp_up", (15.0, 30.0))},
            "Phyco": {"high": MembershipFunction("ramp_up", (0.35, 0.60))},
            "Sat": {"high": MembershipFunction("ramp_up", (0.35, 0.55))},
            "Visual": {"bloom": MembershipFunction("ramp_up", (0.40, 0.70))},
            "Rain": {"high": MembershipFunction("ramp_up", (10.0, 30.0))},
            "LandLoad": {"high": MembershipFunction("ramp_up", (0.40, 0.70))},
        }
    )


def _check_optional_length(name: str, values: Sequence[object], optional: Sequence[object] | None) -> None:
    if optional is not None and len(optional) != len(values):
        raise ValueError(f"{name} length must match values length")


def eco_and_scalar(
    values: Sequence[float],
    reliabilities: Sequence[float] | None = None,
    weights: Sequence[float] | None = None,
    lam: float = 0.5,
    eps: float = 1e-12,
) -> float:
    _check_optional_length("reliabilities", values, reliabilities)
    _check_optional_length("weights", values, weights)
    vals = [clip01(value) for value in values]
    if not vals:
        return 0.0
    lam = clip01(lam)
    reliability_values = list(reliabilities) if reliabilities is not None else [1.0] * len(vals)
    weight_values = list(weights) if weights is not None else [1.0] * len(vals)
    rw = [max(0.0, float(rho)) * max(0.0, float(weight)) for rho, weight in zip(reliability_values, weight_values, strict=True)]
    if sum(rw) <= eps:
        rw = [1.0] * len(vals)
    min_part = min(vals)
    geom = exp(sum(weight * safe_log(value, eps) for weight, value in zip(rw, vals, strict=True)) / (sum(rw) + eps))
    return clip01(lam * min_part + (1.0 - lam) * geom)


def eco_and(
    values: Sequence[Interval],
    reliabilities: Sequence[float] | None = None,
    weights: Sequence[float] | None = None,
    lam: float = 0.5,
) -> Interval:
    if not values:
        return (0.0, 0.0)
    return interval_clip01(
        (
            eco_and_scalar([interval[0] for interval in values], reliabilities, weights, lam),
            eco_and_scalar([interval[1] for interval in values], reliabilities, weights, lam),
        )
    )


def eco_or(
    values: Sequence[Interval],
    reliabilities: Sequence[float] | None = None,
    weights: Sequence[float] | None = None,
    lam: float = 0.5,
) -> Interval:
    if not values:
        return (0.0, 0.0)
    return interval_not(eco_and([interval_not(value) for value in values], reliabilities, weights, lam))


def combine_reliabilities(values: Sequence[float], independences: Sequence[float] | None = None) -> float:
    _check_optional_length("independences", values, independences)
    independence_values = list(independences) if independences is not None else [1.0] * len(values)
    prod = 1.0
    any_positive = False
    for value, independence in zip(values, independence_values, strict=True):
        reliability = clip01(value) * clip01(independence)
        any_positive = any_positive or reliability > 0.0
        prod *= 1.0 - reliability
    return clip01(1.0 - prod) if any_positive else 0.0


@dataclass
class MIFALEDT2:
    config: MIFALConfig = field(default_factory=MIFALConfig)
    state: Interval | None = None

    def __post_init__(self) -> None:
        self.state = interval_clip01(self.config.initial_state if self.state is None else self.state)
        self.validate_config()

    def current_state(self) -> Interval:
        return interval_clip01(self.config.initial_state if self.state is None else self.state)

    def validate_config(self) -> None:
        if self.config.chl_alert <= self.config.chl_base:
            raise ValueError("chl_alert must be greater than chl_base")
        if self.config.tau_c_days <= 0 or self.config.tau_memory_days <= 0:
            raise ValueError("time constants must be positive")
        bounded_names = [
            "alpha_precaution",
            "lambda_N",
            "lambda_P",
            "lambda_R",
            "lambda_L",
            "lambda_H",
            "lambda_D",
            "lambda_M",
            "lambda_G",
        ]
        for name in bounded_names:
            value = getattr(self.config, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        required_maps = [
            self.config.tau_var,
            self.config.default_sigma,
            self.config.uncertainty_floor,
            self.config.missing_bonus,
            self.config.sample_cost,
            self.config.variable_bounds,
        ]
        for variable in self.config.priors:
            for mapping in required_maps:
                if variable not in mapping:
                    raise ValueError(f"Missing configuration for variable {variable!r}")
            if variable not in self.config.membership:
                raise ValueError(f"Missing membership functions for variable {variable!r}")
        for variable, functions in self.config.membership.items():
            if not functions:
                raise ValueError(f"Variable {variable!r} has no membership functions")
            for label, mf in functions.items():
                try:
                    mf.validate()
                except ValueError as exc:
                    raise ValueError(f"Invalid membership for {variable!r}/{label!r}: {exc}") from exc

    def sanitize_value(self, variable: str, value: float) -> float:
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"Non-finite value for variable {variable!r}")
        bounds = self.config.variable_bounds.get(variable)
        if bounds is None:
            return numeric
        lo, hi = bounds
        if lo <= numeric <= hi:
            return numeric
        if self.config.strict_physical_bounds:
            raise ValueError(f"Value {numeric!r} for variable {variable!r} outside physical bounds {bounds!r}")
        return min(max(numeric, lo), hi)

    def fuse_variable(self, variable: str, raw: RawInput | None) -> FusedValue:
        if variable not in self.config.priors and not self.config.allow_unknown_variables:
            raise KeyError(f"Unknown variable {variable!r}. Set allow_unknown_variables=True to keep it as metadata.")
        obs = as_observations(raw)
        prior = self.config.priors.get(variable, 0.0)
        default_sigma = self.config.default_sigma.get(variable, 1.0)
        tau = self.config.tau_var.get(variable, 7.0)
        if not obs:
            return FusedValue(prior, max(default_sigma, 1e-12), 0.0, False, 999.0, 0)

        values: list[float] = []
        weights: list[float] = []
        sigmas: list[float] = []
        ages: list[float] = []
        reliabilities: list[float] = []
        independences: list[float] = []
        for observation in obs:
            try:
                value = self.sanitize_value(variable, observation.value)
            except ValueError:
                if self.config.strict_physical_bounds:
                    raise
                continue
            cv = 0.0 if observation.cv is None else max(0.0, float(observation.cv))
            quality = clip01(observation.source_quality)
            fit = clip01(observation.source_fit)
            age = max(0.0, float(observation.age_days))
            sigma = observation.sigma if observation.sigma is not None else (cv * abs(value) if observation.cv is not None else default_sigma)
            sigma = max(float(sigma), 1e-12)
            scale = max(abs(value), default_sigma, 1e-12)
            cv_eff = cv + sigma / scale
            reliability = clip01(quality * fit * exp(-age / max(tau, 1e-12)) / (1.0 + cv_eff))
            values.append(value)
            weights.append(reliability)
            sigmas.append(sigma)
            ages.append(age)
            reliabilities.append(reliability)
            independences.append(clip01(observation.independence))

        wsum = sum(weights)
        if wsum <= 1e-12:
            age_out = max(ages) if ages else 999.0
            return FusedValue(prior, max(default_sigma, 1e-12), 0.0, False, age_out, len(obs))

        xhat = sum(weight * value for weight, value in zip(weights, values, strict=True)) / wsum
        rho = combine_reliabilities(reliabilities, independences)
        age_mean = sum(weight * age for weight, age in zip(weights, ages, strict=True)) / wsum
        norm_w = [weight / wsum for weight in weights]
        measurement_var = sum((weight**2) * (sigma**2) for weight, sigma in zip(norm_w, sigmas, strict=True))
        disagreement_var = sum(weight * ((value - xhat) ** 2) for weight, value in zip(weights, values, strict=True)) / wsum
        return FusedValue(xhat, sqrt(max(measurement_var + disagreement_var, 1e-12)), rho, True, age_mean, len(obs))

    def fuse_all(self, data: Mapping[str, RawInput]) -> dict[str, FusedValue]:
        unknown = sorted(set(data) - set(self.config.priors))
        if unknown and not self.config.allow_unknown_variables:
            raise KeyError(f"Unknown input variables: {unknown!r}")
        variables = set(self.config.priors) | (set(data) if self.config.allow_unknown_variables else set())
        return {variable: self.fuse_variable(variable, data.get(variable)) for variable in sorted(variables)}

    def rho(self, fused: Mapping[str, FusedValue], *variables: str) -> float:
        values = [fused[variable].reliability for variable in variables if variable in fused]
        return combine_reliabilities(values) if values else 0.0

    def mu(self, fused: Mapping[str, FusedValue], variable: str, label: str) -> Interval:
        fv = fused[variable]
        mf = self.config.membership[variable][label]
        extra = self.config.uncertainty_floor.get(variable, fv.sigma) * (1.0 - fv.reliability)
        if not fv.available:
            extra += self.config.missing_bonus.get(variable, 0.0)
        return mf.interval(fv.value, fv.sigma + extra, fv.reliability)

    def compute_indices(self, fused: Mapping[str, FusedValue]) -> dict[str, Interval]:
        cfg = self.config
        theta = self.mu(fused, "Tw", "favorable")
        temp_high = self.mu(fused, "Tw", "high")
        temp_unfav = interval_not(theta)

        tp_high = self.mu(fused, "TP", "high")
        tp_medium = self.mu(fused, "TP", "medium")
        tp_pressure = eco_or(
            [tp_high, interval_scale(tp_medium, 0.65)],
            [self.rho(fused, "TP"), self.rho(fused, "TP")],
            lam=cfg.lambda_N,
        )
        nutrient_terms = [tp_pressure]
        nutrient_rhos = [self.rho(fused, "TP")]
        if fused["TN"].available:
            tn_sufficient = self.mu(fused, "TN", "sufficient")
            nutrient_terms.append(
                eco_and([tp_pressure, tn_sufficient], [self.rho(fused, "TP"), self.rho(fused, "TN")], lam=cfg.lambda_N)
            )
            nutrient_rhos.append(self.rho(fused, "TP", "TN"))

        do_low = self.mu(fused, "DOb", "low")
        strat_high = self.mu(fused, "Strat", "high")
        if fused["DOb"].available or fused["Strat"].available:
            internal_p = eco_and(
                [do_low, temp_high, strat_high],
                [self.rho(fused, "DOb"), self.rho(fused, "Tw"), self.rho(fused, "Strat")],
                lam=cfg.lambda_P,
            )
            internal_p_rho = self.rho(fused, "DOb", "Tw", "Strat")
        else:
            internal_p = (0.0, 0.55)
            internal_p_rho = 0.05
        nutrient_terms.append(internal_p)
        nutrient_rhos.append(internal_p_rho)

        if fused["Rain"].available or fused["LandLoad"].available:
            runoff = eco_and(
                [self.mu(fused, "Rain", "high"), self.mu(fused, "LandLoad", "high")],
                [self.rho(fused, "Rain"), self.rho(fused, "LandLoad")],
                lam=cfg.lambda_R,
            )
            nutrient_terms.append(runoff)
            nutrient_rhos.append(self.rho(fused, "Rain", "LandLoad"))
        else:
            runoff = (0.0, 0.35)
        nutrients = eco_or(nutrient_terms, nutrient_rhos, lam=cfg.lambda_N)

        light_terms: list[Interval] = []
        light_rhos: list[float] = []
        if fused["Secchi"].available:
            light_terms.append(self.mu(fused, "Secchi", "adequate"))
            light_rhos.append(self.rho(fused, "Secchi"))
        turb_high = self.mu(fused, "Turb", "high")
        if fused["Turb"].available:
            light_terms.append(interval_not(turb_high))
            light_rhos.append(self.rho(fused, "Turb"))
        light = eco_and(light_terms, light_rhos, lam=cfg.lambda_L) if light_terms else (0.15, 0.85)

        stability_terms: list[Interval] = []
        stability_rhos: list[float] = []
        if fused["Wind"].available:
            stability_terms.append(self.mu(fused, "Wind", "low"))
            stability_rhos.append(self.rho(fused, "Wind"))
        if fused["Residence"].available:
            stability_terms.append(self.mu(fused, "Residence", "high"))
            stability_rhos.append(self.rho(fused, "Residence"))
        if fused["Strat"].available:
            stability_terms.append(strat_high)
            stability_rhos.append(self.rho(fused, "Strat"))
        stability = eco_and(stability_terms, stability_rhos, lam=cfg.lambda_H) if stability_terms else (0.0, 0.80)

        disturbance_terms: list[Interval] = []
        disturbance_rhos: list[float] = []
        if fused["Wind"].available:
            disturbance_terms.append(self.mu(fused, "Wind", "high"))
            disturbance_rhos.append(self.rho(fused, "Wind"))
        if fused["Flushing"].available:
            disturbance_terms.append(self.mu(fused, "Flushing", "high"))
            disturbance_rhos.append(self.rho(fused, "Flushing"))
        if fused["Turb"].available:
            disturbance_terms.append(turb_high)
            disturbance_rhos.append(self.rho(fused, "Turb"))
        if fused["Tw"].available:
            disturbance_terms.append(temp_unfav)
            disturbance_rhos.append(self.rho(fused, "Tw"))
        disturbance = eco_or(disturbance_terms, disturbance_rhos, lam=cfg.lambda_D) if disturbance_terms else (0.0, 0.70)

        memory_terms: list[Interval] = []
        memory_rhos: list[float] = []
        for variable, label in [("Chl_prev", "high"), ("Phyco", "high"), ("Sat", "high"), ("Visual", "bloom")]:
            if fused[variable].available:
                decay = exp(-fused[variable].age_days / max(cfg.tau_memory_days, 1e-12))
                memory_terms.append(interval_scale(self.mu(fused, variable, label), decay))
                memory_rhos.append(self.rho(fused, variable))
        memory = eco_or(memory_terms, memory_rhos, lam=cfg.lambda_M) if memory_terms else (0.0, 0.35)

        growth = eco_and(
            [theta, nutrients, light, stability],
            [
                self.rho(fused, "Tw"),
                self.rho(fused, "TP", "TN"),
                self.rho(fused, "Secchi", "Turb"),
                self.rho(fused, "Wind", "Residence", "Strat"),
            ],
            lam=cfg.lambda_G,
        )
        return {
            "Theta": theta,
            "Nutrients": nutrients,
            "Light": light,
            "Stability": stability,
            "Disturbance": disturbance,
            "Memory": memory,
            "Growth": growth,
            "InternalP": internal_p,
            "Runoff": runoff,
        }

    def forecast_state(self, indices: Mapping[str, Interval], dt_days: float, state: Interval | None = None) -> Interval:
        cfg = self.config
        b = interval_clip01(self.current_state() if state is None else state)
        b_lo, b_hi = b
        g_lo, g_hi = indices["Growth"]
        m_lo, m_hi = indices["Memory"]
        d_lo, d_hi = indices["Disturbance"]
        scale = 1.0 - exp(-max(0.0, dt_days) / max(cfg.tau_c_days, 1e-12))
        gamma_lo = cfg.gamma0 + cfg.gammaG * g_lo + cfg.gammaM * m_lo
        gamma_hi = cfg.gamma0 + cfg.gammaG * g_hi + cfg.gammaM * m_hi
        loss_lo = cfg.delta0 + cfg.deltaD * d_lo
        loss_hi = cfg.delta0 + cfg.deltaD * d_hi
        q_lo, q_hi = logistic_factor_interval(b)
        inv_lo, inv_hi = 1.0 - b_hi, 1.0 - b_lo
        next_lo = b_lo + scale * (gamma_lo * q_lo + cfg.eta * g_lo * inv_lo - loss_hi * b_hi)
        next_hi = b_hi + scale * (gamma_hi * q_hi + cfg.eta * g_hi * inv_hi - loss_lo * b_lo)
        return interval_clip01((next_lo, next_hi))

    def chl_to_risk_interval(self, fv: FusedValue) -> Interval:
        cfg = self.config
        base = max(cfg.chl_base, 1e-12)
        alert = max(cfg.chl_alert, base + 1e-12)
        uncertainty = fv.sigma + cfg.uncertainty_floor.get("Chl", fv.sigma) * (1.0 - fv.reliability)
        if not fv.available:
            uncertainty += cfg.missing_bonus.get("Chl", 0.0)
        lo = max(fv.value - uncertainty, 1e-12)
        hi = max(fv.value + uncertainty, 1e-12)
        denominator = safe_log(alert) - safe_log(base)
        return interval_clip01(((safe_log(lo) - safe_log(base)) / denominator, (safe_log(hi) - safe_log(base)) / denominator))

    def observation_interval(self, fused: Mapping[str, FusedValue]) -> tuple[Interval | None, float]:
        terms: list[Interval] = []
        rhos: list[float] = []
        if fused["Chl"].available:
            terms.append(self.chl_to_risk_interval(fused["Chl"]))
            rhos.append(fused["Chl"].reliability)
        if fused["Sat"].available:
            terms.append(self.mu(fused, "Sat", "high"))
            rhos.append(fused["Sat"].reliability)
        if fused["Visual"].available:
            visual_membership = self.mu(fused, "Visual", "bloom")
            visual_interval = eco_or([visual_membership, (0.0, 0.35)], [fused["Visual"].reliability, 0.10], lam=0.40)
            terms.append(visual_interval)
            rhos.append(fused["Visual"].reliability)
        if not terms:
            return None, 0.0
        return eco_or(terms, rhos, lam=0.35), combine_reliabilities(rhos)

    def assimilate(self, forecast: Interval, observation: Interval, rho_obs: float, sigma_obs: float = 0.0) -> Interval:
        forecast = interval_clip01(forecast)
        observation = interval_clip01(observation)
        width_f = forecast[1] - forecast[0]
        width_y = observation[1] - observation[0]
        gain = clip01(rho_obs / (rho_obs + width_f + width_y + max(0.0, sigma_obs) + 1e-12))
        lo = (1.0 - gain) * forecast[0] + gain * observation[0]
        hi = (1.0 - gain) * forecast[1] + gain * observation[1]
        return interval_clip01((lo, hi))

    def index_scores(self, indices: Mapping[str, Interval]) -> dict[str, float]:
        return {name: conservative_risk(interval, self.config.alpha_precaution) for name, interval in indices.items()}

    def predict_from_fused(self, fused: Mapping[str, FusedValue], dt_days: float, assimilate: bool = True) -> Interval:
        indices = self.compute_indices(fused)
        analysis_state = self.current_state()
        if assimilate:
            obs, rho_obs = self.observation_interval(fused)
            if obs is not None:
                analysis_state = self.assimilate(self.current_state(), obs, rho_obs)
        return self.forecast_state(indices, dt_days, state=analysis_state)

    def overall_data_reliability(self, fused: Mapping[str, FusedValue]) -> float:
        groups = [
            ["Tw"],
            ["TP", "TN"],
            ["Secchi", "Turb"],
            ["Wind", "Residence", "Strat"],
            ["Chl", "Chl_prev", "Phyco", "Sat", "Visual"],
        ]
        scores: list[float] = []
        for group in groups:
            vals = [fused[variable].reliability for variable in group if variable in fused and fused[variable].available]
            scores.append(max(vals) if vals else 0.0)
        return clip01(sum(scores) / len(scores)) if scores else 0.0

    def expected_measurement_value(self, variable: str, current: FusedValue, base_risk: float) -> float:
        if current.available and isfinite(current.value):
            return current.value
        risk = clip01(base_risk)
        if variable in {"Chl", "Chl_prev"}:
            base = max(self.config.chl_base, 1e-12)
            alert = max(self.config.chl_alert, base + 1e-12)
            return exp(safe_log(base) + risk * (safe_log(alert) - safe_log(base)))
        if variable in {"Phyco", "Sat", "Visual", "Strat", "LandLoad"}:
            return risk
        return current.value

    def value_of_information(self, fused: Mapping[str, FusedValue], dt_days: float, variables: Sequence[str] | None = None) -> dict[str, float]:
        if variables is None:
            variables = [
                "Tw",
                "TP",
                "TN",
                "Secchi",
                "Turb",
                "Wind",
                "Residence",
                "Flushing",
                "Strat",
                "DOb",
                "Chl",
                "Chl_prev",
                "Phyco",
                "Sat",
                "Visual",
                "Rain",
                "LandLoad",
            ]
        base_interval = self.predict_from_fused(fused, dt_days, assimilate=True)
        base_risk = conservative_risk(base_interval, self.config.alpha_precaution)
        base_width = base_interval[1] - base_interval[0]
        out: dict[str, float] = {}
        for variable in variables:
            if variable not in fused:
                continue
            fv = fused[variable]
            delta = max(self.config.default_sigma.get(variable, 1.0), 0.05 * max(abs(fv.value), 1.0))
            if not isfinite(delta) or delta <= 0.0:
                continue
            f_plus, f_minus, f_fresh = dict(fused), dict(fused), dict(fused)
            f_plus[variable] = replace(fv, value=fv.value + delta)
            f_minus[variable] = replace(fv, value=fv.value - delta)
            r_plus = conservative_risk(self.predict_from_fused(f_plus, dt_days, assimilate=True), self.config.alpha_precaution)
            r_minus = conservative_risk(self.predict_from_fused(f_minus, dt_days, assimilate=True), self.config.alpha_precaution)
            local_effect = 0.5 * abs(r_plus - r_minus)
            expected_value = self.expected_measurement_value(variable, fv, base_risk)
            fresh_sigma = max(self.config.default_sigma.get(variable, fv.sigma), 1e-12)
            f_fresh[variable] = replace(
                fv,
                value=expected_value,
                sigma=fresh_sigma,
                reliability=max(fv.reliability, 0.90),
                available=True,
                age_days=0.0,
            )
            fresh_interval = self.predict_from_fused(f_fresh, dt_days, assimilate=True)
            fresh_width = fresh_interval[1] - fresh_interval[0]
            fresh_risk = conservative_risk(fresh_interval, self.config.alpha_precaution)
            uncertainty_gain = max(0.0, base_width - fresh_width)
            risk_shift = abs(base_risk - fresh_risk)
            cost = max(self.config.sample_cost.get(variable, 1.0), 1e-12)
            out[variable] = (1.0 - fv.reliability) * (local_effect + uncertainty_gain + 0.25 * risk_shift) / cost
        return dict(sorted(out.items(), key=lambda item: item[1], reverse=True))

    def step(
        self,
        data: Mapping[str, RawInput],
        dt_days: float = 7.0,
        assimilate: bool = True,
        update_state: bool = False,
        state_update_target: str = "forecast",
        compute_voi: bool = True,
    ) -> dict[str, object]:
        fused = self.fuse_all(data)
        indices = self.compute_indices(fused)
        state_prior = self.current_state()
        obs, rho_obs = self.observation_interval(fused)
        state_analysis = state_prior
        if assimilate and obs is not None:
            state_analysis = self.assimilate(state_prior, obs, rho_obs)

        forecast = self.forecast_state(indices, dt_days, state=state_analysis)
        risk_interval = interval_clip01(forecast)
        risk_cons = conservative_risk(risk_interval, self.config.alpha_precaution)
        uncertainty = risk_interval[1] - risk_interval[0]
        interval_confidence = clip01(1.0 - uncertainty)
        data_reliability = self.overall_data_reliability(fused)
        operational_confidence = clip01(interval_confidence * (0.5 + 0.5 * data_reliability))
        scores = self.index_scores(indices)
        voi = self.value_of_information(fused, dt_days) if compute_voi else {}
        result: dict[str, object] = {
            "model_version": __version__,
            "risk_interval": risk_interval,
            "risk_conservative": risk_cons,
            "uncertainty": uncertainty,
            "interval_confidence": interval_confidence,
            "data_reliability": data_reliability,
            "confidence": operational_confidence,
            "alert_class": self.alert_class(risk_cons),
            "state_prior": state_prior,
            "state_after_observation_assimilation": state_analysis,
            "forecast_interval": forecast,
            "observation_interval": obs,
            "observation_reliability": rho_obs,
            "indices": indices,
            "index_scores": scores,
            "dominant_factors": sorted(scores.items(), key=lambda item: item[1], reverse=True),
            "voi": voi,
            "recommended_sampling": next(iter(voi), None),
            "fused": fused,
        }
        if update_state:
            target = state_update_target.lower()
            if target == "forecast":
                self.state = risk_interval
            elif target == "analysis":
                self.state = state_analysis
            else:
                raise ValueError("state_update_target must be 'forecast' or 'analysis'")
        return result

    @staticmethod
    def alert_class(risk: float) -> str:
        value = clip01(risk)
        if value < 0.25:
            return "low"
        if value < 0.50:
            return "watch"
        if value < 0.75:
            return "high"
        return "critical"

    def reset(self, state: Interval | None = None) -> None:
        self.state = interval_clip01(self.config.initial_state if state is None else state)


def interval_coverage(observations: Sequence[float], intervals: Sequence[Interval]) -> float:
    """Empirical coverage of interval forecasts."""

    if len(observations) != len(intervals):
        raise ValueError("observations and intervals must have the same length")
    if not observations:
        return 0.0
    hits = 0
    for observation, interval in zip(observations, intervals, strict=True):
        lo, hi = interval
        if lo <= float(observation) <= hi:
            hits += 1
    return hits / len(observations)


def winkler_interval_score(observation: float, interval: Interval, alpha: float = 0.10) -> float:
    """Winkler score for a central (1 - alpha) prediction interval."""

    alpha = max(float(alpha), 1e-12)
    lo, hi = interval
    value = float(observation)
    width = max(0.0, hi - lo)
    if value < lo:
        return width + 2.0 * (lo - value) / alpha
    if value > hi:
        return width + 2.0 * (value - hi) / alpha
    return width


def interval_sugeno_zero_order(weight_intervals: Sequence[Interval], consequents: Sequence[float], eps: float = 1e-12, max_iter: int = 100) -> Interval:
    """Karnik-Mendel style type-reduction for zero-order interval Sugeno rules."""

    if len(weight_intervals) != len(consequents):
        raise ValueError("weights and consequents must have the same length")
    for consequent in consequents:
        if not isfinite(float(consequent)):
            raise ValueError("consequents must be finite")
    if not weight_intervals:
        return (0.0, 0.0)
    pairs = sorted(
        [(clip01(consequent), interval_clip01(weight)) for weight, consequent in zip(weight_intervals, consequents, strict=True)],
        key=lambda pair: pair[0],
    )
    c = [pair[0] for pair in pairs]
    wl = [pair[1][0] for pair in pairs]
    wu = [pair[1][1] for pair in pairs]
    if sum(wu) <= eps:
        return interval_clip01((min(c), max(c)))

    def avg(weights: Sequence[float]) -> float:
        denominator = sum(weights)
        return 0.0 if denominator <= eps else clip01(sum(weight * consequent for weight, consequent in zip(weights, c, strict=True)) / denominator)

    y = avg([(lo + hi) * 0.5 for lo, hi in zip(wl, wu, strict=True)])
    for _ in range(max_iter):
        k = max([index for index, consequent in enumerate(c) if consequent <= y], default=-1)
        y_new = avg([wu[index] if index <= k else wl[index] for index in range(len(c))])
        if abs(y_new - y) < 1e-10:
            break
        y = y_new
    left = y

    y = avg([(lo + hi) * 0.5 for lo, hi in zip(wl, wu, strict=True)])
    for _ in range(max_iter):
        k = max([index for index, consequent in enumerate(c) if consequent <= y], default=-1)
        y_new = avg([wl[index] if index <= k else wu[index] for index in range(len(c))])
        if abs(y_new - y) < 1e-10:
            break
        y = y_new
    return interval_clip01((left, y))
