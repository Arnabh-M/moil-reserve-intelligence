"""Background ingestion scheduler (APScheduler).

- `ingest_satellite_data` (every 6h): STILL a stub — becomes the Google
  Earth Engine ingestion job.
- `run_watcher` (every 5min): LIVE — runs `WatcherAgent.check_for_changes()`
  to detect new equipment/production risks and mirror them into Postgres +
  Neo4j. Wrapped so any failure inside the agent is logged and recorded as a
  failed job run, but never propagates far enough to stop the scheduler or
  crash the app.

`start_scheduler()` / `stop_scheduler()` are called from app.main's FastAPI
lifespan. Both are safe to call more than once in the same process (guarded
by `scheduler.running`), so re-entering startup never double-starts the
scheduler or duplicates its jobs.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("oresight.scheduler")

scheduler = BackgroundScheduler(timezone="UTC")

_job_status: dict[str, dict[str, Any]] = {}

# Last time the watcher completed a pass, so each run only looks at changes
# since the previous one. `None` -> WatcherAgent falls back to its own
# "last 6 hours" default on the first run.
_watcher_last_run_at: datetime | None = None

# Lightweight last-result snapshot for the watcher, surfaced in logs (and
# available for /admin if ever needed) without depending on APScheduler's
# own event bookkeeping.
_watcher_last_result: dict[str, Any] = {
    "ran_at": None,
    "created_count": None,
    "error": None,
}


def ingest_satellite_data() -> None:
    """STUB: replaced later with real Google Earth Engine ingestion."""
    logger.info(
        "GEE ingestion placeholder — no-op (%s)",
        datetime.now(timezone.utc).isoformat(),
    )


def run_watcher() -> None:
    """Run one WatcherAgent pass. Never lets an agent failure escape.

    A raised exception here would be caught by APScheduler and logged, and
    the scheduler would keep running — but we catch it ourselves too so the
    job is still counted as executed (not left in a way that could wedge a
    misconfigured executor) and so the failure detail lands in our own log
    and last-result snapshot.
    """
    global _watcher_last_run_at

    # Imported lazily so importing this module (e.g. in tests that only need
    # start/stop) doesn't drag in the model + driver stack.
    from app.agents.watcher import WatcherAgent
    from app.db import SessionLocal
    from app.graph_db import init_graph_driver

    started_at = datetime.now(timezone.utc)
    since = _watcher_last_run_at
    db = None
    try:
        db = SessionLocal()
        driver = init_graph_driver()
        agent = WatcherAgent(db, driver)
        created = agent.check_for_changes(since=since)
        _watcher_last_run_at = started_at
        _watcher_last_result.update(
            ran_at=started_at, created_count=len(created), error=None
        )
        logger.info(
            "Watcher run complete (since=%s): %d new risk event(s)",
            since.isoformat() if since else "default(-6h)",
            len(created),
        )
    except Exception as exc:  # noqa: BLE001 - a watcher failure must not stop the scheduler
        _watcher_last_result.update(
            ran_at=started_at, created_count=None, error=repr(exc)
        )
        logger.exception("Watcher run failed — scheduler continues")
    finally:
        if db is not None:
            db.close()


def _record_job_event(event: JobExecutionEvent) -> None:
    now = datetime.now(timezone.utc)
    if event.exception:
        _job_status[event.job_id] = {
            "last_run_at": now,
            "last_status": "error",
            "last_error": str(event.exception),
        }
        logger.error("Job %s failed: %s", event.job_id, event.exception)
    else:
        _job_status[event.job_id] = {
            "last_run_at": now,
            "last_status": "success",
            "last_error": None,
        }


def start_scheduler() -> None:
    """Register jobs and start the scheduler. Safe to call more than once."""
    if scheduler.running:
        return

    scheduler.add_job(
        ingest_satellite_data,
        trigger="interval",
        hours=6,
        id="ingest_satellite_data",
        replace_existing=True,
    )
    scheduler.add_job(
        run_watcher,
        trigger="interval",
        minutes=5,
        id="run_watcher",
        replace_existing=True,
    )
    scheduler.add_listener(_record_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [j.id for j in scheduler.get_jobs()])


def stop_scheduler() -> None:
    """Stop the scheduler cleanly. Safe to call even if it isn't running."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_jobs_status() -> list[dict[str, Any]]:
    """Return each registered job's id, next run time, and last run status."""
    jobs = []
    for job in scheduler.get_jobs():
        status = _job_status.get(job.id, {})
        jobs.append(
            {
                "id": job.id,
                "next_run_time": job.next_run_time,
                "last_run_at": status.get("last_run_at"),
                "last_status": status.get("last_status", "never_run"),
                "last_error": status.get("last_error"),
            }
        )
    return jobs
