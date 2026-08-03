"""Session-wide deterministic CPU controls for Closure V1 tests."""

from __future__ import annotations


def pytest_sessionstart() -> None:
    """Lock Torch threads before any test can start parallel work."""
    try:
        import torch
    except ImportError:
        return
    if torch.get_num_threads() != 1:
        torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
