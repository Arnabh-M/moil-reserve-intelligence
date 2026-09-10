"""Single source of truth for inbound request-schema bounds — physically
impossible values only, never business-policy limits (see Prohibition #6 of
the "bounded value validation" task: err generous, block the impossible).

Mirrored in the frontend at src/constants/validationLimits.js — that file
must agree with this one. If you change a value here, change it there too.

Scope note: this list is intentionally short. It covers exactly the fields
identified in discovery as both (a) user-supplied on an inbound request
schema and (b) currently unbounded. Fields that already carry a tighter,
proven bound (e.g. SimulateRequest.duration_days at 1-90, quality_grade at
0-100, operating/downtime_hours at 0-24, SiteNoteCreate.text at 4000 chars)
are deliberately left untouched — the existing bound wins over any generic
constant here. See app/schemas/production.py, blasting.py, simulation.py,
site_note.py for those.
"""

# Tonnage: no single blast, shift, or record in a mining operation of this
# scale physically produces more than 100,000 tonnes in one entry. Applies
# to production actual/target output, material processed, and blast
# expected/actual yield tonnes — all "how many tonnes of ore" quantities.
MAX_TONNES = 100_000

# Free-text reason/note fields with no existing bound (e.g. equipment status
# change reason). Generous ceiling against unbounded-length abuse, not a
# business policy on note length.
MAX_FREE_TEXT_LENGTH = 5000

# Scenario Simulator condition duration, in days. SimulateRequest.duration_days
# already has its own tighter, validated bound (1-90, see schemas/simulation.py)
# and is NOT touched by this constant. ConditionInput.duration has no existing
# bound, so it gets the generic simulator-lever range instead.
SIMULATOR_CONDITION_DURATION_MIN_DAYS = 1
SIMULATOR_CONDITION_DURATION_MAX_DAYS = 365

# Simulator severity is a percentage (see the severity_min_pct/severity_max_pct
# naming used throughout app/routers/simulate.py's training-range fallback and
# the "Severity {sev}%..." OOD warning text) — 0-100 is the physical bound of
# a percentage, not a guess. The highest ceiling actually used across all
# three scenario types (equipment_down/delay_blasting/rainfall_event) is
# 100.0 (rainfall_event), so this bound never rejects a legitimate value that
# out-of-distribution detection already flags as merely unusual.
SEVERITY_PCT_MIN = 0
SEVERITY_PCT_MAX = 100
