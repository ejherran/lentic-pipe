"""Small typing helpers for dynamic pandas workflows."""

from __future__ import annotations

from collections.abc import Hashable, Iterator
from typing import Any, cast

import pandas as pd


def dataframe_rows(frame: pd.DataFrame) -> Iterator[Any]:
    """Iterate DataFrame rows as dynamic namedtuple rows.

    Pandas report-building code often consumes DataFrame rows with
    ``itertuples(index=False)`` and accesses runtime column names as attributes.
    Static type checkers cannot infer those generated attributes, so this helper
    contains that dynamic boundary in one place instead of spreading broad
    ignores through report code.
    """

    return cast(Iterator[Any], frame.itertuples(index=False))


def group_key_tuple(key: Hashable) -> tuple[Any, ...]:
    """Normalize pandas group keys to a tuple.

    Pandas returns a scalar key for single-column groupby operations and a tuple
    key for multi-column operations, but its type hints expose both as
    ``Hashable``. Keeping the conversion here avoids repeating casts at every
    dynamic groupby boundary.
    """

    if isinstance(key, tuple):
        return key
    return (key,)


def year_month_month(values: pd.Series) -> pd.Series:
    """Return the calendar month for `YYYY-MM` string-like values."""

    return pd.to_datetime(values.astype(str), format="%Y-%m", errors="coerce").dt.month


def year_month_year(values: pd.Series) -> pd.Series:
    """Return the calendar year for `YYYY-MM` string-like values."""

    return pd.to_datetime(values.astype(str), format="%Y-%m", errors="coerce").dt.year
