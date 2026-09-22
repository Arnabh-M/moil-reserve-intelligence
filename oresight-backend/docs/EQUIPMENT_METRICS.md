# Equipment performance metrics (Task 6, backend)

Availability, failures, MTBF, MTTR, and a maintenance-due flag, per machine
and per site — covers problem statement SIH26009's "equipment performance"
input and its "equipment downtime" constraint.

Endpoints: `GET /equipment/metrics` (fleet, optionally filtered to one
site) and `GET /equipment/{equipment_id}/metrics` (one machine, plus a
weekly series and the raw downtime events). See the CONTRACT in
`TASK6_equipment_metrics_backend_prompt.md` for the exact response shapes —
this document explains the definitions, mappings, and assumptions behind
them. Implementation: `app/services/equipment_metrics.py`,
`app/constants/equipment_assumptions.py`,
`app/routers/equipment.py` (`/metrics` routes), `app/schemas/equipment.py`.

## Where the data comes from

`equipment_status_log` is the append-only history table Field Intake
Hardening Phase 4 added for the audit log / flap detection. Until this task,
the only thing that ever wrote to it was `POST /equipment/{id}/status`, so a
freshly-seeded database had **no** downtime history at all —
`scripts/import_p2_data.py` reads `data/equipment_downtime_log.csv` only to
set `Equipment.last_status_change`, and it actively *deletes*
`equipment_status_log` rows for the equipment it reimports without ever
writing new ones back.

`scripts/backfill_equipment_status_log.py` closes that gap: for every row in
`data/equipment_downtime_log.csv` it inserts two `equipment_status_log`
rows (`up`→`down` at `down_start`, `down`→`up` at `down_end`), both tagged
`source="downtime_log_import"`. This is what the metrics below are actually
computed from. See "Running the backfill" below.

## Interval reconstruction

For one machine, its full `equipment_status_log` history (every source —
backfilled *and* live `PATCH` rows — merged into one chronological stream,
since a machine can only be in one real state at a time) is walked in order
and turned into downtime intervals:

- each `down` is paired with the next `up` — that's one interval;
- a trailing `down` with no following `up` yet is an **open interval**,
  ended at `min(now, window_end)`;
- a status that repeats the previous one (e.g. re-posting `down` while
  already down, just to update the reason text) is a **duplicate
  consecutive status** — skipped, not treated as a second interval starting
  over.

Every interval is then **clipped** to the requested analysis window
(`[window_start, window_end)`) — an interval can start before the window,
end after it, or both; only the portion inside the window counts toward
that window's hours.

## Reason → category mapping

Every downtime interval is assigned exactly one category, from the reason
recorded on its `down` row:

1. **Exact match** against `REASON_CATEGORIES` (case-insensitive) — the
   fixed vocabulary `data/equipment_downtime_log.csv` actually uses:

   | Category | Reasons |
   |---|---|
   | `planned_maintenance` | scheduled maintenance |
   | `failure` | electrical fault, hydraulic leak, mechanical failure |
   | `spare_parts_wait` | spare parts unavailable |
   | `operational` | operator shift gap |
   | `weather` | weather delay |

2. Otherwise, **keyword rules** (case-insensitive substring match, first
   match wins) for free-text reasons typed into the field-intake form:

   | Keywords (substring) | Category |
   |---|---|
   | maintenance, service, pm | `planned_maintenance` |
   | fault, leak, failure, breakdown, broken, burst, seized | `failure` |
   | spare, parts | `spare_parts_wait` |
   | operator, shift, crew | `operational` |
   | rain, weather, flood, waterlog, storm | `weather` |

3. No match → `other`.

### Why weather and operator-shift-gap downtime don't count against physical availability

`physical_availability` only deducts `planned_maintenance` + `failure` +
`spare_parts_wait` hours. `weather` and `operational` downtime still reduce
`overall_availability` (the machine genuinely wasn't producing), but not
physical availability, because in both cases **the machine itself was not
broken** — it was idle for a reason external to its own condition (weather
shut down the site; the operator/crew wasn't there). Physical availability
is meant to answer "was this machine mechanically capable of running,"
which those two categories don't compromise. `other` is not deducted from
physical availability either, on the same reasoning: it's an
unrecognized/unclassified reason, not a confirmed mechanical cause, so it's
treated the same as weather/operational rather than assumed to be a
failure.

## Definitions and formulas

Let `window_hours` = hours in `[window_start, window_end)`, and let a
machine's downtime hours in that window be split by category as above.

```
physical_availability_pct = (window_hours − planned_maintenance − failure − spare_parts_wait) / window_hours × 100
overall_availability_pct  = (window_hours − all downtime hours) / window_hours × 100
mtbf_hours = (window_hours − all downtime hours) / failures      (null when failures == 0)
mttr_hours = mean duration of failure-category intervals only    (null when failures == 0)
```

`failures` = count of downtime intervals categorized `failure` in the
window. Percentages are 0–100 with one decimal place; hours are rounded to
two decimals.

**Fleet totals are always the sum of hours/counts across machines, never an
average of per-machine percentages** — e.g. fleet `physical_availability_pct`
is computed from `sum(window_hours across machines)` and
`sum(deduction hours across machines)`, the same formula applied at fleet
scale, not `mean(machine.physical_availability_pct)`. Averaging percentages
directly would silently misweight machines with different downtime, and
would not equal the true fleet-wide fraction of available time.

### `top_failure_reason`

ASSUMPTION (not in the original DEFINITIONS, filled in here): the raw
reason string that occurs most often among a machine's `failure`-category
intervals in the window; ties broken by total hours, then alphabetically,
for a deterministic result. `null` if the machine had no failures in the
window.

### Maintenance status

- `last_maintenance_at` = the end of the **latest** `planned_maintenance`
  interval up to the window end — computed from the machine's **full**
  status-log history, not just the window-clipped portion, so a maintenance
  event before a short analysis window still counts.
- `next_maintenance_due` = `last_maintenance_at.date() + MAINTENANCE_INTERVAL_DAYS`.
- `days_since_last_maintenance` = days between `last_maintenance_at` and the
  window end.
- `maintenance_status`:
  - `unknown` — no `planned_maintenance` interval found at all;
  - `overdue` — `next_maintenance_due` is before the window end;
  - `due_soon` — due within `DUE_SOON_DAYS` of the window end;
  - `ok` — otherwise.

The window end (not real wall-clock "now") is the reference point for all
of this, because the demo dataset is historical (ends 2026-08-30) — see
"Window resolution" below.

### Weekly series (per-equipment endpoint only)

One entry per ISO week (Monday-start) overlapping the analysis window,
labeled by that week's Monday even when the first/last bucket is partial
(the window doesn't start/end on a Monday). Each week's
`downtime_hours`/`failures`/`physical_availability_pct` are computed with
the exact same formulas above, scoped to that week's hours.

## `utilisation_pct` is always `null`

There is no operating-hours (hour-meter) data anywhere in this dataset —
`equipment_status_log` only knows up/down, never "ran for N hours today."
Utilisation (actual operating time ÷ available time) cannot be computed
without that, so it's hardcoded `null` with
`utilisation_note: "Needs operating-hours (hour-meter) data"`. This is
never estimated or approximated.

## Assumptions and their environment variables

All in `app/constants/equipment_assumptions.py`, each overridable via an
environment variable without a code change (not added to
`app/config.py`'s `Settings` — out of scope for this task's allowed files):

| Constant | Default | Env var | Why it's a placeholder |
|---|---|---|---|
| `MAINTENANCE_INTERVAL_DAYS` | 30 | `EQUIPMENT_MAINTENANCE_INTERVAL_DAYS` | Calendar-based because there's no hour-meter data; a real schedule is usually hour-based (e.g. "every 250 operating hours"). Replace with MOIL's real schedule when known. |
| `DUE_SOON_DAYS` | 7 | `EQUIPMENT_DUE_SOON_DAYS` | No MOIL-specific lead-time is known. |
| `DEFAULT_WINDOW_DAYS` | 90 | `EQUIPMENT_METRICS_DEFAULT_WINDOW_DAYS` | Generic "recent quarter," not a MOIL policy. |
| `MAX_WINDOW_DAYS` | 366 | `EQUIPMENT_METRICS_MAX_WINDOW_DAYS` | Generous ceiling against unbounded-range abuse, not a business rule. |
| `REASON_CATEGORIES` / `KEYWORD_RULES` | see above | — (not single scalars, not env-overridable) | The reason vocabulary and grouping is a placeholder for MOIL's real downtime-reason taxonomy. |

One extra caveat on `KEYWORD_RULES`: matching is plain case-insensitive
**substring** containment, not whole-word matching, per the task spec. The
`pm` keyword (→ `planned_maintenance`) is the riskiest one — it's short
enough to appear inside unrelated words. It was checked against this
dataset's actual reason strings and the exact-match categories with no
false positives, but a future free-text reason like "compressor down"
containing an incidental `pm`-adjacent substring is worth watching if this
ships past the demo. (In practice `pm`'s specific letter order makes
accidental matches rarer than it looks — words like "compressor" and
"pump" contain `mp`, not `pm` — but this is still a substring rule, not a
semantic one.)

## Window resolution

- Default window: `end` = the date of `data_through` (the latest
  `equipment_status_log.changed_at` in scope — site-filtered, single
  machine, or all equipment), or today if that scope has no history yet;
  `start` = `end − DEFAULT_WINDOW_DAYS`.
- A window covers whole calendar days: `start` at 00:00:00 UTC, `end`
  through 23:59:59 UTC (implemented as an exclusive boundary at the next
  day's midnight).
- If that exclusive end boundary would fall in the future, it's clipped to
  real wall-clock `now` — this only matters if a caller explicitly requests
  a future `end` date, or if `equipment_status_log`'s latest row happens to
  be very recent; the demo dataset itself is historical and doesn't trigger
  this.
- Validation: `start` after `end` → 422. Resolved window longer than
  `MAX_WINDOW_DAYS` → 422 (checked after defaulting, so an explicit `start`
  with no `end` is checked too).

## Running the backfill

```bash
cd oresight-backend
python -m scripts.backfill_equipment_status_log            # writes
python -m scripts.backfill_equipment_status_log --dry-run   # report only
```

Requires equipment to already exist (run after `app.seed_dev` /
`scripts.import_p2_data`, e.g. as part of `scripts/rebuild_demo_db.py`).
Maps each CSV `equipment_id` code (e.g. `eq_bal_03`) to a Postgres
`Equipment` row by **site + name**, reusing (not duplicating)
`scripts.import_p2_data._parse_equipment_roster` against
`seed_graph.cypher` — Postgres's `Equipment` table has no column for that
code. Safe to re-run: in one transaction it deletes and reinserts only
`source="downtime_log_import"` rows for the equipment it touches; rows from
any other source (`manual`/`bulk`/`sync`) are never touched. It never
changes `Equipment.status` or `Equipment.last_status_change` — those stay
exactly as `import_p2_data` set them, so the watcher agent
(`app/agents/watcher.py`), which only ever reads those two columns (never
`equipment_status_log`), can't be affected by anything this script writes.
Because the CSV's dates are historical (ending 2026-08-30), the backfilled
rows are always far outside flap detection's `EQUIPMENT_FLAP_WINDOW_HOURS`
(24h default) trailing window, so they can't trip a false flap alert on the
next live status change either.

## Follow-ups (after all Task 6 branches merge)

1. Add the backfill as one step in `scripts/rebuild_demo_db.py`, after
   `scripts.import_p2_data` (and after the second `app.seed_dev` pass, so it
   runs against the final equipment roster) — so a fresh demo DB has
   downtime history without a manual extra step.
2. Run `python -m scripts.export_contract` once, to regenerate
   `docs/openapi.json` / `docs/API_CONTRACT.md` with the two new endpoints
   (not run on this branch per the parallel-work rules).
