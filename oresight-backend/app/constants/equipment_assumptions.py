"""Equipment performance metrics — assumptions with no source-of-truth data
yet (Task 6, backend). Every numeric assumption here is a placeholder for
MOIL's actual maintenance schedule / reason taxonomy and is overridable via
an environment variable so it can be tuned without a code change. These are
intentionally NOT added to app/config.py's Settings class (out of scope for
this task's allowed-files list) — read directly from the environment here
instead.
"""

import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


# ASSUMPTION: calendar-based maintenance interval. MOIL equipment has no
# hour-meter data in this dataset, so a real (usually hour-based, e.g. "every
# 250 operating hours") maintenance schedule can't be computed — 30 calendar
# days is a placeholder cadence. Replace with MOIL's real schedule (ideally
# hour-based, once hour-meter readings are available) when known.
MAINTENANCE_INTERVAL_DAYS = _int_env("EQUIPMENT_MAINTENANCE_INTERVAL_DAYS", 30)

# ASSUMPTION: a machine due for maintenance within this many days is flagged
# "due_soon" rather than "ok". No MOIL-specific lead time is known yet.
DUE_SOON_DAYS = _int_env("EQUIPMENT_DUE_SOON_DAYS", 7)

# ASSUMPTION: default analysis window when the caller doesn't specify
# start/end. 90 days is a generic "recent quarter" default, not a MOIL policy.
DEFAULT_WINDOW_DAYS = _int_env("EQUIPMENT_METRICS_DEFAULT_WINDOW_DAYS", 90)

# Hard ceiling on how wide a caller-supplied window can be (422 beyond this).
# Generous ceiling against unbounded-range abuse, not a business policy.
MAX_WINDOW_DAYS = _int_env("EQUIPMENT_METRICS_MAX_WINDOW_DAYS", 366)

# Exact (case-insensitive) reason -> category mapping, for the fixed reason
# vocabulary used by data/equipment_downtime_log.csv. Checked before
# KEYWORD_RULES. ASSUMPTION: this vocabulary and grouping is a placeholder —
# replace with MOIL's real downtime-reason taxonomy when available.
REASON_CATEGORIES: dict[str, list[str]] = {
    "planned_maintenance": ["scheduled maintenance"],
    "failure": ["electrical fault", "hydraulic leak", "mechanical failure"],
    "spare_parts_wait": ["spare parts unavailable"],
    "operational": ["operator shift gap"],
    "weather": ["weather delay"],
}

# Free-text keyword rules for reasons typed into the field-intake form (i.e.
# not an exact match against REASON_CATEGORIES). Case-insensitive substring
# match, checked in order, first match wins; no match -> "other".
# ASSUMPTION: plain substring matching, not whole-word matching — e.g. "pm"
# matches inside a longer word too. Chosen for simplicity per the task spec;
# revisit if false-positive category assignments show up in real field data.
KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["maintenance", "service", "pm"], "planned_maintenance"),
    (["fault", "leak", "failure", "breakdown", "broken", "burst", "seized"], "failure"),
    (["spare", "parts"], "spare_parts_wait"),
    (["operator", "shift", "crew"], "operational"),
    (["rain", "weather", "flood", "waterlog", "storm"], "weather"),
]

# The fixed set of category keys every downtime_hours_by_category dict must
# have, in contract order.
CATEGORY_KEYS: tuple[str, ...] = (
    "planned_maintenance",
    "failure",
    "spare_parts_wait",
    "operational",
    "weather",
    "other",
)

# utilisation_pct is always null (see CONTRACT) — there is no operating-hours
# (hour-meter) data anywhere in this dataset to compute it from.
UTILISATION_NOTE = "Needs operating-hours (hour-meter) data"

DATA_NOTE = (
    "Downtime history loaded from the downtime log and field entries; demo "
    "data is synthetic until MOIL maintenance records are connected."
)
