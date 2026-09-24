"""Sign-correctness sweep for the Simulator: does a disruption move the forecast the right way?

For every day in a span, every site and every scenario, run the SimulatorAgent and count the days on
which the "after" production forecast is LOWER than "before" (a disruption must not raise output).
Run over the same days for the CURRENT model and, with --old-rev, for the simulator + model as they
were at an earlier git revision, so the two are compared on an identical subset and never against a
number measured on a different span.

    python -m scripts.simulator_sweep                                  # current model, 2026-01-01..2026-09-22
    python -m scripts.simulator_sweep --old-rev 1084074                # ... and the old model, same days
    python -m scripts.simulator_sweep --old-rev 1084074 --old-full-year   # harness check: old model, all of 2026
    python -m scripts.simulator_sweep --old-rev 1084074 --old-calendar-only --old-full-year   # the other replay

HOW EACH MODEL IS REPLAYED. The current simulator takes `as_of`: the whole feature row (rain, downtime,
backlog, blast delays, calendar) is rebuilt from data strictly before that day. The old simulator has
no such notion: its features came from `datetime.now()` (calendar + a cosine rainfall proxy) and the
CURRENT database state (equipment status, trailing shortfall), so replaying it means faking `now()`;
only its date-derived features vary. That is exactly how its direction was found to flip with the date
(tests/test_smoke.py's old xfail note), and it is why --old-full-year exists: it must reproduce that
note's Balaghat equipment_down figure (212 of 365 days correct) before the old-model numbers are trusted.

Requests are the smoke test's: {scenario_type, site_id, duration_days: 5}, no severity (rainfall_event
then uses the model's default, the Medium training level). The Neo4j graph traversal is stubbed out: it
does not affect the forecast and would only slow a ~2,400-run sweep.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Site  # noqa: E402

SCENARIOS = ("equipment_down", "delay_blasting", "rainfall_event")
DURATION_DAYS = 5


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=k) for k in range((end - start).days + 1)]


def _stub_graph(agent) -> None:
    agent._traverse_graph = lambda *a, **k: ([], {"nodes": [], "edges": []})


def load_old_agent_class(rev: str, workdir: Path, calendar_only: bool = False):
    """The simulator module and shipped model exactly as committed at `rev`, loaded from a temp copy."""
    for rel in (
        "app/agents/simulator.py",
        "models/shortfall_forecaster.pkl",
        "models/feature_columns.json",
        "models/model_metrics.json",
    ):
        blob = subprocess.check_output(["git", "show", f"{rev}:oresight-backend/{rel}"], cwd=REPO_ROOT)
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    spec = importlib.util.spec_from_file_location("old_simulator", workdir / "app/agents/simulator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # MODELS_DIR resolves to workdir/models

    class FakeNow(datetime):
        """`now()` for the old simulator. With calendar_only the instant stays REAL (so its equipment
        downtime window is measured against the real DB timestamps) and only the calendar features it reads
        (date(), weekday(), month) are those of the replayed day; otherwise the whole instant is the replayed day."""

        fixed: datetime = datetime.now(timezone.utc)
        calendar_only: bool = False

        @classmethod
        def now(cls, tz=None):
            if not cls.calendar_only:
                return cls.fixed
            real = datetime.now(tz)
            return cls(real.year, real.month, real.day, real.hour, real.minute, real.second, real.microsecond, tzinfo=real.tzinfo)

        def date(self):
            return self.fixed.date() if self.calendar_only else super().date()

        def weekday(self):
            return self.fixed.weekday() if self.calendar_only else super().weekday()

        @property
        def month(self):
            return self.fixed.month if self.calendar_only else super().month

    FakeNow.calendar_only = calendar_only
    module.datetime = FakeNow
    return module.SimulatorAgent, FakeNow


def _tally(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "days": n,
        "production_lower": sum(r["after_t"] < r["before_t"] for r in rows),
        "production_equal": sum(r["after_t"] == r["before_t"] for r in rows),
        "production_higher": sum(r["after_t"] > r["before_t"] for r in rows),
        "risk_not_lower": sum(r["after_risk"] >= r["before_risk"] for r in rows),
        "mean_change_pct": round(100 * sum((r["after_t"] - r["before_t"]) / r["before_t"] for r in rows) / n, 2) if n else None,
    }


def sweep_current(db, days: list[date]) -> dict:
    from app.agents.simulator import SimulatorAgent

    agent = SimulatorAgent(db, None)
    _stub_graph(agent)
    out: dict = {}
    for site in db.scalars(select(Site).order_by(Site.id)).all():
        for scenario in SCENARIOS:
            rows = []
            for d in days:
                r = agent.run_scenario(scenario, site.id, DURATION_DAYS, as_of=d)
                rows.append({
                    "before_t": r["before"]["production_forecast_tonnes"], "after_t": r["after"]["production_forecast_tonnes"],
                    "before_risk": r["before"]["risk_score"], "after_risk": r["after"]["risk_score"],
                })
            out[f"{site.name}/{scenario}"] = _tally(rows)
    return out


def sweep_old(db, days: list[date], rev: str, calendar_only: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        agent_cls, fake_now = load_old_agent_class(rev, Path(tmp), calendar_only)
        agent = agent_cls(db, None)
        _stub_graph(agent)
        out: dict = {}
        for site in db.scalars(select(Site).order_by(Site.id)).all():
            for scenario in SCENARIOS:
                rows = []
                for d in days:
                    fake_now.fixed = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
                    r = agent.run_scenario(scenario, site.id, DURATION_DAYS)
                    rows.append({
                        "before_t": r["before"]["production_forecast_tonnes"], "after_t": r["after"]["production_forecast_tonnes"],
                        "before_risk": r["before"]["risk_score"], "after_risk": r["after"]["risk_score"],
                    })
                out[f"{site.name}/{scenario}"] = _tally(rows)
        return out


def _print(title: str, result: dict) -> None:
    print(f"\n{title}")
    print(f"  {'site / scenario':<28}{'days':>6}{'prod lower':>12}{'equal':>7}{'higher':>8}{'risk>=':>8}{'mean chg':>10}")
    for key, t in result.items():
        print(f"  {key:<28}{t['days']:>6}{t['production_lower']:>12}{t['production_equal']:>7}{t['production_higher']:>8}"
              f"{t['risk_not_lower']:>8}{t['mean_change_pct']:>9}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-09-22")
    parser.add_argument("--old-rev", help="git revision whose simulator + shipped model to sweep on the same days")
    parser.add_argument("--old-full-year", action="store_true", help="also sweep the old model over all of 2026 (harness check)")
    parser.add_argument("--old-calendar-only", action="store_true",
                        help="replay the old model by varying only its calendar features (DB state at real now) instead of faking the whole instant")
    parser.add_argument("--out", help="write results as JSON")
    args = parser.parse_args()

    days = _days(date.fromisoformat(args.start), date.fromisoformat(args.end))
    db = SessionLocal()
    results: dict = {"span": [args.start, args.end], "duration_days": DURATION_DAYS}
    try:
        results["current"] = sweep_current(db, days)
        _print(f"CURRENT model, {args.start}..{args.end}", results["current"])
        if args.old_rev:
            mode = "calendar features only" if args.old_calendar_only else "whole instant faked"
            results["old"] = sweep_old(db, days, args.old_rev, args.old_calendar_only)
            _print(f"OLD model ({args.old_rev}; replay: {mode}), same {len(days)} days", results["old"])
            if args.old_full_year:
                year = _days(date(2026, 1, 1), date(2026, 12, 31))
                results["old_full_year"] = sweep_old(db, year, args.old_rev, args.old_calendar_only)
                _print(f"OLD model ({args.old_rev}), all of 2026 (harness check; expect Balaghat/equipment_down = 212 of 365)",
                       results["old_full_year"])
    finally:
        db.close()
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
