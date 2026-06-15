"""Small adaptive ANFIS building blocks for synthetic Gate 1 validation.

The functions in this module are intentionally minimal. They provide a
trainable Sugeno-style ANFIS surface for synthetic smoke tests before the
project attempts a full real-data adaptive fuzzy layer.
"""

from __future__ import annotations

import importlib
import random
from typing import Any

import numpy as np


def _require_torch() -> Any:
    try:
        return importlib.import_module("torch")
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for adaptive ANFIS. Install the modeling group with Poetry before running this code."
        ) from exc


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch = _require_torch()
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _inverse_softplus(values: Any) -> Any:
    torch = _require_torch()
    safe = torch.clamp(values, min=1e-6)
    return torch.log(torch.expm1(safe))


def _rule_index_tensor(input_dim: int, membership_count: int) -> Any:
    torch = _require_torch()
    grids = torch.meshgrid(
        *[torch.arange(membership_count, dtype=torch.long) for _ in range(input_dim)],
        indexing="ij",
    )
    return torch.stack([grid.reshape(-1) for grid in grids], dim=1)


def make_adaptive_anfis(
    *,
    input_dim: int,
    membership_count: int = 3,
    min_width: float = 0.03,
    min_gap: float = 1e-4,
    output_activation: str = "sigmoid",
    center_constraint: str = "ordered",
) -> Any:
    """Create a small ordered Gaussian-membership Sugeno ANFIS model.

    The returned model exposes helper methods used by tests and smoke reports:
    `ordered_centers`, `positive_widths`, `gaussian_memberships`,
    `firing_strengths`, and `centers_are_ordered`.
    """

    if input_dim <= 0:
        raise ValueError("input_dim must be positive")
    if membership_count < 2:
        raise ValueError("membership_count must be at least 2")
    if min_width <= 0:
        raise ValueError("min_width must be positive")
    if min_gap < 0:
        raise ValueError("min_gap must be non-negative")
    if output_activation not in {"sigmoid", "clip"}:
        raise ValueError("output_activation must be 'sigmoid' or 'clip'")
    if center_constraint not in {"ordered", "unit"}:
        raise ValueError("center_constraint must be 'ordered' or 'unit'")
    if center_constraint == "unit" and min_gap * (membership_count + 1) >= 1.0:
        raise ValueError("min_gap is too large for unit-constrained centers")

    torch = _require_torch()

    class AdaptiveANFISModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.input_dim = int(input_dim)
            self.membership_count = int(membership_count)
            self.min_width = float(min_width)
            self.min_gap = float(min_gap)
            self.output_activation = output_activation
            self.center_constraint = center_constraint
            initial_widths = torch.full((input_dim, membership_count), 0.25, dtype=torch.float32)
            if center_constraint == "unit":
                margin = max(0.05, float(min_gap) * 2.0)
                margin = min(margin, 0.45)
                unit_centers = torch.linspace(margin, 1.0 - margin, membership_count, dtype=torch.float32)
                unit_gaps = torch.cat(
                    [
                        unit_centers[:1],
                        torch.diff(unit_centers),
                        1.0 - unit_centers[-1:],
                    ]
                )
                residual = 1.0 - float(min_gap) * (membership_count + 1)
                proportions = torch.clamp((unit_gaps - float(min_gap)) / residual, min=1e-6)
                self.raw_center_gaps = torch.nn.Parameter(torch.log(proportions).repeat(input_dim, 1))
                self.register_parameter("first_center", None)
                self.register_parameter("raw_deltas", None)
            else:
                initial_centers = torch.linspace(0.0, 1.0, membership_count, dtype=torch.float32).repeat(input_dim, 1)
                spacing = torch.diff(initial_centers, dim=1) - float(min_gap)
                spacing = torch.clamp(spacing, min=1e-3)
                self.first_center = torch.nn.Parameter(initial_centers[:, 0].clone())
                self.raw_deltas = torch.nn.Parameter(_inverse_softplus(spacing))
                self.register_parameter("raw_center_gaps", None)
            self.raw_widths = torch.nn.Parameter(_inverse_softplus(initial_widths - float(min_width)))
            self.consequent_weights = torch.nn.Parameter(torch.zeros(self.rule_count, input_dim, dtype=torch.float32))
            self.consequent_bias = torch.nn.Parameter(torch.zeros(self.rule_count, dtype=torch.float32))
            self.register_buffer("rule_indices", _rule_index_tensor(input_dim, membership_count))

        @property
        def rule_count(self) -> int:
            return int(self.membership_count**self.input_dim)

        def ordered_centers(self) -> Any:
            if self.center_constraint == "unit":
                residual = 1.0 - self.min_gap * (self.membership_count + 1)
                gaps = self.min_gap + residual * torch.nn.functional.softmax(self.raw_center_gaps, dim=1)
                return torch.cumsum(gaps[:, :-1], dim=1)
            deltas = torch.nn.functional.softplus(self.raw_deltas) + self.min_gap
            return torch.cat([self.first_center[:, None], self.first_center[:, None] + torch.cumsum(deltas, dim=1)], dim=1)

        def centers_in_unit_interval(self, tolerance: float = 1e-7) -> bool:
            centers = self.ordered_centers().detach()
            return bool(
                (
                    torch.all(centers >= -float(tolerance))
                    & torch.all(centers <= 1.0 + float(tolerance))
                ).item()
            )

        def positive_widths(self) -> Any:
            return torch.nn.functional.softplus(self.raw_widths) + self.min_width

        def centers_are_ordered(self, tolerance: float = 1e-7) -> bool:
            centers = self.ordered_centers().detach()
            return bool(torch.all(torch.diff(centers, dim=1) >= -float(tolerance)).item())

        def gaussian_memberships(self, x: Any) -> Any:
            centers = self.ordered_centers().to(device=x.device, dtype=x.dtype)
            widths = self.positive_widths().to(device=x.device, dtype=x.dtype)
            scaled = (x[:, :, None] - centers[None, :, :]) / widths[None, :, :]
            return torch.exp(-0.5 * scaled**2)

        def firing_strengths(self, x: Any) -> Any:
            memberships = self.gaussian_memberships(x)
            rule_indices = self.rule_indices.to(device=x.device)
            per_feature = [
                memberships[:, feature_index, rule_indices[:, feature_index]]
                for feature_index in range(self.input_dim)
            ]
            return torch.stack(per_feature, dim=0).prod(dim=0)

        def forward(self, x: Any, return_details: bool = False) -> Any:
            firing = self.firing_strengths(x)
            normalized = firing / torch.clamp(firing.sum(dim=1, keepdim=True), min=1e-12)
            rule_outputs = x @ self.consequent_weights.to(dtype=x.dtype).T + self.consequent_bias.to(dtype=x.dtype)
            raw_output = (normalized * rule_outputs).sum(dim=1)
            if self.output_activation == "sigmoid":
                prediction = torch.sigmoid(raw_output)
            else:
                prediction = torch.clamp(raw_output, 0.0, 1.0)
            if not return_details:
                return prediction
            return {
                "prediction": prediction,
                "firing_strengths": firing,
                "normalized_firing_strengths": normalized,
                "rule_outputs": rule_outputs,
                "centers": self.ordered_centers(),
                "widths": self.positive_widths(),
            }

    return AdaptiveANFISModel()


def parameter_snapshot(model: Any) -> dict[str, Any]:
    return {name: parameter.detach().clone() for name, parameter in model.named_parameters()}


def max_parameter_delta(model: Any, before: dict[str, Any]) -> float:
    max_delta = 0.0
    for name, parameter in model.named_parameters():
        if name not in before:
            continue
        delta = (parameter.detach() - before[name]).abs().max().item()
        max_delta = max(max_delta, float(delta))
    return max_delta


def train_supervised_anfis(
    model: Any,
    features: np.ndarray,
    target: np.ndarray,
    *,
    epochs: int = 100,
    learning_rate: float = 0.05,
    random_seed: int = 1729,
    grad_clip: float = 1.0,
) -> list[dict[str, float]]:
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")

    set_reproducible_seed(random_seed)
    torch = _require_torch()
    x = torch.as_tensor(features, dtype=torch.float32)
    y = torch.as_tensor(target, dtype=torch.float32).reshape(-1)
    if x.ndim != 2:
        raise ValueError("features must be a 2D array")
    if len(x) != len(y):
        raise ValueError("features and target must contain the same row count")

    optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate), weight_decay=0.0)
    curve: list[dict[str, float]] = []
    for epoch in range(1, int(epochs) + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        prediction = model(x)
        loss = torch.nn.functional.mse_loss(prediction, y)
        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(grad_clip))
        optimizer.step()
        curve.append({"epoch": float(epoch), "loss": float(loss.detach().item())})
    return curve
