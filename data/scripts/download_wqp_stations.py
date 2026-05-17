#!/usr/bin/env python3
"""Download WQP Station/search data into data/raw/wqp/wqp_stations.csv."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from data.scripts.wqp_download_common import parse_args, run, stations_config


if __name__ == "__main__":
    sys.exit(run(stations_config(), parse_args(__doc__ or "")))
