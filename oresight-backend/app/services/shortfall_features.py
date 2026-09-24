"""Shortfall-forecaster feature math that TRAINING AND INFERENCE MUST SHARE.

numpy/pandas-free on purpose (stdlib only) so the root-level training pipeline
(shortfall_feature_engineering.py) can import it without the backend's DB/settings
import chain, and so the API and the trainer literally execute the same function.
There must never be a second implementation of a feature that both sides use: a
definition that drifts between training and serving is a silent accuracy bug.
tests/test_shortfall_feature_sharing.py enforces this by patching the shared
function and requiring the training frame to change with it.

Currently shared: blast_delay_days_lag (the model's highest-importance feature).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

BLAST_LAG_WINDOW_DAYS = 7

# Longest delay the model ever saw in training (scripts/synthetic_operations.py:
# BLAST_DELAY_DURATION_DAYS = (1, 4); tests/test_shortfall_feature_sharing.py
# asserts these stay equal). A delayed blast with no recorded new date is an
# open-ended delay; counting it as lasting longer than anything in training would
# push the feature out of distribution, so it is treated as lasting at most this
# many days from its planned date.
BLAST_DELAY_MAX_DAYS = 4


def as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def blast_delay_days_lag(events: Iterable[tuple[date, int]], t: date | datetime) -> float:
    """Number of distinct blast-delay days in the trailing window t-7 .. t-1.

    `events` are (planned_date, delay_days): an event occupies the calendar days
    planned_date .. planned_date + delay_days - 1. Only days strictly before t are
    counted, so a delay still in progress at the start of t contributes exactly the
    days it has already run - never any future day. Overlapping events are
    counted once per calendar day.
    """
    t_date = as_date(t)
    window_start = t_date - timedelta(days=BLAST_LAG_WINDOW_DAYS)
    delay_days: set[date] = set()
    for planned, n_days in events:
        first = as_date(planned)
        for k in range(int(n_days)):
            d = first + timedelta(days=k)
            if window_start <= d < t_date:
                delay_days.add(d)
    return float(len(delay_days))
