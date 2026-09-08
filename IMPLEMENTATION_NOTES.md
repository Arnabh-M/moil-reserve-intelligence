# Field Intake Hardening — Implementation Notes

Status: **Phases 1–4 complete and verified. Not yet committed** — see
"Commit status" below. Phases 5–10 (§4.1–4.3, §5.2–5.3, §7) are **not
implemented** — see "What was deliberately skipped" below for why, and for a
scoping recommendation if this work continues.

## Commit status

Nothing in this document has been committed. The working tree carries
Phases 1–4 uncommitted, on top of unrelated merge conflicts elsewhere that
need to be sorted first. Do not assume a clean checkpoint exists before
Phase 4 — the diff includes Phases 1–3 as well.

## Before this task: a data-integrity incident, resolved

A previous session attempting this same task was killed mid-work. It had
already run Phase 1 and Phase 2's migrations against the local dev
Postgres database before dying, without committing the migration files.
The working tree was reverted to `origin/main`, but the database was left
with the resulting columns/tables physically present while
`alembic_version` still pointed at a revision (`c51abfbe1bf8`) that no
longer existed in the codebase — `alembic current` failed outright.

This was resolved in two steps, both non-destructive (all 551 seeded
production records and 15 site notes were preserved throughout):

1. **Diagnosed** via `alembic current`/`history` plus direct schema
   inspection (`\d production_records` etc.) to confirm the DB was
   genuinely ahead of the code, not just the version marker.
2. **Repaired** via `alembic stamp --purge ddd398038e1a` — repoints the
   version marker to the actual code baseline without running any DDL.

When Phase 1/2's models were then rewritten to match, `alembic revision
--autogenerate` correctly produced an **empty diff** against this dev DB
(the physical schema already matched). That empty migration would have
been silently wrong on any fresh database (CI, a new clone, prod), so the
migration file was hand-written as **conditional DDL** (`ADD COLUMN IF NOT
EXISTS`, `CREATE TABLE IF NOT EXISTS`, and `DO $$ ... $$` existence guards
around the constraint swap) instead of the auto-generated body. This makes
the one migration file simultaneously correct as a real schema-creating
migration on a fresh database and a safe no-op re-application on this
orphaned one. Verified via:
- `alembic upgrade head` on this dev DB — succeeded as a no-op, `alembic
  current` correctly advanced to head, row counts unchanged.
- The repo's own `tests/test_migrations.py` (which builds fresh throwaway
  databases) — both tests pass, proving the same migration genuinely
  creates the schema from scratch, not just no-ops.
- `alembic downgrade -1` on this dev DB **correctly failed** with a
  `UniqueViolation` — because leftover test data (two production records
  for the same site+date under different shifts, `id` 742/743) is
  genuinely incompatible with the old 2-column unique constraint. This is
  expected, not a bug: once a constraint-loosening migration is used for
  real, downgrading past that usage without deleting data is inherently
  impossible. The failure rolled back cleanly (transactional DDL); no data
  was lost, and `alembic current` remained at head afterward.

## Phase 1 — Production tab persistence (§3)

**The core fix.** The Production tab collected operating hours, downtime
hours, material processed, quality grade, and shortfall reasons, then
discarded all of it on submit — only `actual_output`/`target_output` ever
reached the server. Fixed end-to-end.

**Backend:**
- `ProductionRecord` gains 12 new columns, all nullable or
  server-defaulted: `shift` (NOT NULL, default `'general'`),
  `operating_hours`, `downtime_hours`, `material_processed`,
  `quality_grade`, `shortfall_reasons` (Postgres `text[]`),
  `shortfall_other_note`, `variance_class`, `created_at`, `updated_at`,
  `created_by`, `updated_by`.
- New `production_record_audit` table (append-only: `record_id`, `field`,
  `old_value`, `new_value`, `changed_by`, `changed_at`) — one row per
  changed field on every `PATCH`.
- Unique constraint swapped from `(site_id, date)` to
  `(site_id, date, shift)`, using the exact backfill-then-swap order the
  task specified (new constraint created before the old one is dropped —
  never a moment without a duplicate guard).
- `ShortfallReason` vocabulary and the variance-classification thresholds
  live in one place (`app/schemas/production.py`) and are served via
  `GET /production/shortfall-reasons` and `GET /production/thresholds` —
  the frontend imports them instead of hardcoding a second copy.
- `POST /production` validates `operating_hours + downtime_hours <= 24`,
  requires `shortfall_reasons` when `variance_class == 'significantly_below'`,
  and requires `shortfall_other_note` when `'other'` is selected. The 409
  message now names the shift when it isn't `'general'`.
- `PATCH /production/{id}` — partial update, re-runs all validation against
  the *resulting* record, gated by `PRODUCTION_EDIT_WINDOW_HOURS` (403
  outside the window), writes one audit row per changed field.
- 11 automated tests in `tests/test_production.py`, all passing.

**Frontend:**
- Shift selector (Day/Night/General, defaults to General).
- All 11 collected fields now sent on submit — verified live via direct
  API calls and a DB query (not just visually).
- Shortfall chips and variance thresholds fetched from the backend, with
  the old hardcoded lists kept only as a fetch-failure fallback.
- `operating_hours + downtime_hours <= 24` validated client-side too.
- Edit affordance: selecting a site/date/shift that already has a record
  loads it into the form in "edit" mode (banner shows who/when it was last
  touched) and submit becomes a `PATCH`. 403 (edit window expired) shows
  distinct copy from 409 (conflict).
- `mockData.js` production rows carry the same 18-field shape as the live
  endpoint.

**What was NOT built:** the "Shift note" free-text field is still
UI-only — no column for it was in the task's field table, so it's not
persisted, matching the original app's behavior for that one field.

## Phase 2 — Notes tab site selector (§6)

- Hardcoded `site_id: 1` removed. A site `<select>` (same markup/pattern as
  Equipment/Production/Blasting) now drives both `GET /site-notes/search`
  and `POST /site-notes`.
- Verified live: a note created for site 2 does not appear in a site-1
  search, and vice versa (backend site filtering was already correct going
  in — confirmed by inspection before touching anything).
- Kept the "empty search + default site (Balaghat) reuses the workspace's
  preloaded notes, no extra request" behavior; only switching to a
  non-default site or typing a query triggers a fresh fetch.
- `SiteNote` gained `updated_at` (nullable) and `revision` (int, default 1)
  — groundwork only, per the task's own instruction. No update endpoint
  exists yet to use them.

## Phase 3 — Geology upload limit + mock/live contract drift (§5.1, §5.4)

- New `GET /config/upload-limits` (`{max_report_bytes, allowed_mime}`) —
  single source of truth. Frontend fetches it on mount; the stale
  hardcoded 25 MB client-side check (real server limit was always 10 MB)
  is gone, replaced by the fetched value with a 10 MB fallback.
- **Option A taken**, as instructed: `ReportUploadOut` now genuinely
  returns `site`, `report_date`, `author`, `report_type`, `page_count`,
  `mineral_candidates[]`, `locations[]`, `estimated_grade_summary`,
  `geological_observations[]`, `extracted_text_preview`,
  `extraction_method` — all previously mock-only fields the frontend was
  already rendering against nothing in live mode.
  - `page_count`/`author`/`report_date` come from the PDF's own
    document-info metadata (`app/services/pdf_text.py:extract_pdf_metadata`).
  - `mineral_candidates`, `locations`, `estimated_grade_summary`,
    `geological_observations`, `report_type` are deterministic
    keyword/regex heuristics over the same text `RegexDepositExtractor`
    already parses (`app/services/extraction.py`) — explicitly not OCR,
    not an LLM, and documented as such in the code. Every one degrades to
    `null`/`[]` rather than guessing.
  - `site` is resolved via the existing `_match_site` belt/zone-matching
    logic already used for the Neo4j write path, just also exposed as a
    display name on the response.
  - `extraction_method` is `"pypdf"` or `"none"` today; `"ocr"` is Phase 6,
    not implemented.
- `geological_observations` changed from a single string (mock-only,
  never matched any real shape) to `list[str]`, matching the task's
  `geological_observations[]`. Both `mockData.js` and `GeologyTab.jsx`'s
  render logic were updated together so they don't drift again.
- **Not implemented in this phase** (they're Phase 6): `report_id` and
  `duplicate` require the `GeologyReport` storage table and
  content-hash dedup logic from §5.2, which wasn't reached. `mockData.js`
  correctly has neither field, so there's no drift — just an honest
  absence on both sides.
- Verified: all 13 pre-existing `tests/test_reports.py` tests still pass
  unchanged — every degrade-to-200 path (unreadable PDF, empty parse,
  Neo4j down) is untouched.
- **A debugging dead end worth recording**: while testing this phase, an
  em dash in one response field appeared as mojibake when displayed
  through this session's own diagnostic tooling (Python `print()` piped
  through the terminal). Checking the *raw response bytes* (hex-dumped,
  which can't be mistranscoded) proved the actual HTTP response was
  correct UTF-8 all along — `e2 80 94`, the exact UTF-8 encoding of the
  em dash. The apparent bug was entirely an artifact of the verification
  method, not the server. The code was still defensively changed to spell
  the em dash as `—` rather than a literal character, which is
  harmless and removes any doubt, but the underlying lesson is: when
  Unicode looks wrong on this Windows setup, check raw bytes before
  concluding it's a data bug.

## Phase 4 — Equipment audit log + flap detection (§2.1, §2.2, §2.4)

**Not built in this phase**: the RTS approval workflow (feature-flagged
resume-to-service approval) from §2's fuller scope — the task explicitly
scoped this phase to §2.1, §2.2, and §2.4 only.

**Backend:**
- New `equipment_status_log` table (append-only): `id`, `equipment_id` (FK,
  indexed), `site_id` (FK, indexed, denormalized off the join), `old_status`,
  `new_status`, `reason`, `changed_by` (default `'system'`), `changed_at`
  (server-default `now()`, indexed), `source` (`manual`/`bulk`/`sync`,
  default `manual`). Composite index `(equipment_id, changed_at DESC)` for
  the newest-first history query. `Equipment.status` is untouched as the
  read path for current status — this table is additive history only.
- `POST /equipment/{id}/status` now writes one log row in the same
  transaction as the status update and the existing `equipment_failure`
  RiskEvent logic — one `db.commit()` covers all three, so a failed log
  insert fails the whole request (intentional, per the task).
- Flap detection: after the log insert, counts that equipment's log rows in
  the trailing `EQUIPMENT_FLAP_WINDOW_HOURS` (default 24) window. Above
  `EQUIPMENT_FLAP_THRESHOLD` (default 4), opens one medium-severity
  `equipment_flapping` RiskEvent (score 0.45), deduped by checking for an
  existing unresolved one for that equipment first — same pattern as
  `equipment_failure`. The response's additive `flapping` field reflects
  the *current* flap state on every call, independent of whether a new
  event was opened this time.
- `EquipmentOut` gained `flapping: bool = False` (additive, default `False`
  on the list endpoint — flap state is only ever computed on the
  status-change call, per the task's scoping, not recomputed on every read).
- `EquipmentStatusUpdate` gained `source: 'manual' | 'bulk' | 'sync' =
  'manual'` (additive, defaults preserve every existing caller's behavior).
- `GET /equipment/{id}/history?limit&before` — cursor-paginated on
  `changed_at`, newest first; `next_cursor` is the last row's timestamp, or
  `null` once a page comes back short of `limit`.
- `GET /equipment/history?site_id&since&limit` — site-wide view, no cursor
  (the task's own spec for this endpoint didn't ask for one).
- 9 new tests in `tests/test_equipment_history.py`: log-row creation,
  `source` defaulting/recording, failure-event dedup across repeated
  `down` posts, flap-event dedup across a >threshold sequence of changes,
  cursor pagination correctness, and 404s for unknown equipment/site.
- Migration `87b25057ff45`: clean `alembic revision --autogenerate` this
  time (unlike Phase 1's `b3c612abd01e`) — the dev DB had no half-applied
  Phase 4 state, so the diff needed no conditional-DDL workaround. Purely
  additive (one new table + 4 indexes, nothing dropped). Verified `upgrade
  head → downgrade -1 → upgrade head` clean, plus both `test_migrations.py`
  fresh-DB tests passing.

**Frontend (Equipment tab):**
- A small history icon next to each row's "Last changed" timestamp (no new
  column — row height stays 42px) opens a right-side panel showing that
  unit's status history, lazily fetched on click (not prefetched for every
  row, per the task — virtualization stays intact).
- Panel supports "Load more" via the cursor, newest-first.
- A ⚠ flapping badge renders inside the existing status cell (not a new
  column) when the row's last status-change response returned
  `flapping: true`.
- Bulk-down flow unchanged except: the confirm button now reads "Confirm N
  units down", and both bulk-up and bulk-down writes carry `source: 'bulk'`.
- `mockData.js` equipment rows gained `flapping: false`; `client.js` gained
  an in-memory `mockEquipmentStatusLog` (same pattern as the existing
  mock blast events) so `VITE_USE_MOCK=true` renders identical history and
  flapping behavior to live mode — verified in both modes via a driven
  browser session (screenshots), not just by reading the code.

**A verification note worth recording**: driving the Equipment tab's status
toggles from outside the app (browser automation) mutates *real* seeded
demo equipment, not throwaway test fixtures — the same endpoint real users
hit. Verifying flap detection this way left one seeded unit (`Compressor
BAL-1`, id 20) stuck `down` with a live `equipment_flapping` RiskEvent and
three duplicate `equipment_failure` events (each a genuinely new up→down
cycle, not a dedup bug). Cleaned up directly in Postgres afterward — the
dedup logic itself is correct: it only suppresses a second event while
already in the same state, not across separate failure cycles, which
matches how a machine actually failing multiple times should behave.
Separately, `tests/test_smoke.py` (pre-existing, not part of this phase)
also posts directly to real seeded equipment without cleanup — over many
repeated `pytest` runs its log rows will eventually accumulate past the
flap threshold and open a real `equipment_flapping` event on that unit.
Worth a test-hygiene fix later; out of scope here.

## What was deliberately skipped (Phases 5–10)

Not attempted, to avoid shipping shallow or broken versions of large
subsystems under time pressure. Each is substantial on its own:

- **§2 (remainder) RTS approval + history UI polish** — the
  feature-flagged resume-to-service approval workflow from §2's fuller
  scope; §2.1/§2.2/§2.4 (audit log, flap detection, history endpoints) are
  done above.
- **§4.1–4.3 Blasting corroboration + permits + explosive ledger** — two
  more new entities with their own CRUD surfaces, a balance-never-negative
  invariant enforced in SQL, and cross-referencing against the equipment
  audit log now available from Phase 4.
- **§5.2–5.3 Geology server-side storage + OCR** — needs a storage
  directory, content-hash dedup, a streaming file endpoint, and optional
  `pytesseract`/`pdf2image` + system packages (`tesseract-ocr`,
  `poppler-utils`) that aren't installed in this environment and weren't
  verified to work here.
- **§7.1 Auth/RBAC** — JWT issuance, a seeded users table with bcrypt, and
  wiring `changed_by`/`created_by` from a real identity instead of the
  literal `'system'` used throughout Phases 1–3.
- **§7.2 Offline queue** — a new `idb-keyval` dependency, FIFO replay with
  backoff, and rerouting every write path in the tab, which the task
  itself places last specifically because it touches already-stable code.
- **§7.3 Neo4j cross-tab edges** — new relationship types tied to the
  equipment log and blasting corroboration work above, so blocked on those.

None of these were started in a half-finished state — nothing here should
be discovered mid-way through by a future session.

## New environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PRODUCTION_EDIT_WINDOW_HOURS` | `48` | Hours after creation a production record's `PATCH` is allowed. |
| `EQUIPMENT_FLAP_WINDOW_HOURS` | `24` | Trailing window for counting an equipment's status changes. |
| `EQUIPMENT_FLAP_THRESHOLD` | `4` | Above this many changes in the window, flap detection trips. |

(`.env.example` updated to match.)

## New migrations

| Revision | Parent | What it does |
|---|---|---|
| `b3c612abd01e` | `ddd398038e1a` | Extends `production_records` (12 columns), adds `production_record_audit`, swaps the production unique constraint to include `shift`, adds `site_notes.updated_at`/`revision`. Written as conditional DDL (see incident section above) — safe to re-run on any DB state. |
| `87b25057ff45` | `b3c612abd01e` | Adds `equipment_status_log` (append-only, 4 indexes incl. the composite `(equipment_id, changed_at DESC)`). Clean autogenerate — no conditional-DDL workaround needed this time. |

Both `alembic upgrade head` (fresh DB, via `tests/test_migrations.py`) and
`alembic upgrade head` (this orphaned dev DB) were verified. `alembic
downgrade -1` was verified to work correctly on a fresh DB and to fail
correctly (not silently) on this dev DB, for the data-integrity reason
explained above. `87b25057ff45`'s own `upgrade head → downgrade -1 →
upgrade head` cycle was verified clean on this dev DB (no data-integrity
conflict — it only adds a table, nothing pre-existing depends on it).

## How to demo what's here

1. `docker compose up -d` (Postgres + Neo4j), then from `oresight-backend`:
   `venv\Scripts\alembic upgrade head` then
   `venv\Scripts\uvicorn app.main:app --reload --port 8000`.
2. From `oresight-frontend`: `pnpm run dev` (works with `VITE_USE_MOCK=true`
   or `false` — both render identically for everything covered here).
3. **Production tab**: fill in operating hours / downtime / material /
   quality grade / a shortfall reason, submit, then re-select the same
   site+date+shift — the form loads in edit mode with the saved values.
   Try `operating_hours=20, downtime_hours=10` for the 422. Try selecting
   "significantly below target" with zero reasons for the other 422.
4. **Notes tab**: switch the site dropdown before searching or adding a
   note — results and the new note are scoped to whichever site is
   selected, not always Balaghat.
5. **Geology tab**: upload `oresight-backend/tests/fixtures/sample_survey.pdf`
   — the extraction panel now shows real site/date/author/page-count/
   mineral-candidate/location/grade-summary/observations data instead of
   empty blocks, in both mock and live mode.
6. **Equipment tab, history**: expand a site group, click the small history
   icon next to any row's "Last changed" time — a side panel loads that
   unit's status history newest-first, with "Load more" once it has more
   than one page.
7. **Equipment tab, flapping**: flip one unit's status dropdown up/down more
   than `EQUIPMENT_FLAP_THRESHOLD` times (default 4) in quick succession —
   a ⚠ badge appears next to its status pill, and a medium-severity
   `equipment_flapping` risk event opens (visible via `GET /risk-events`).
   Repeating the toggle further does not open a second event. Doing this
   against live mode mutates real seeded equipment — reset the unit's
   status and reason afterward if demoing against the shared dev DB.
