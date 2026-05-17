#!/usr/bin/env python3
"""Download the LakeBeD-US CSE dataset snapshot into data/raw/LakeBeD-US-CSE."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data/raw/LakeBeD-US-CSE"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="eco-kgml/LakeBeD-US-CSE",
        repo_type="dataset",
        local_dir=OUTPUT_DIR.as_posix(),
    )
    print(f"LakeBeD-US CSE snapshot available at {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
