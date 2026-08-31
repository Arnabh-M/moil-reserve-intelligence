"""Background ingestion scheduler skeleton (APScheduler).

Two placeholder jobs today; real logic plugs in later:

- `ingest_satellite_data` (every 6h): STUB, becomes the Google Earth Engine
  ingestion job.
- `run_watcher` (every 5min): STUB, becomes the ML teammate's Watcher agent
  on Day 3.

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


def ingest_satellite_data() -> None:
    """STUB: replaced on Day 3 with real Google Earth Engine ingestion."""
    logger.info(
        "GEE ingestion placeholder — no-op (%s)",
        datetime.now(timezone.utc).isoformat(),
    )


def run_watcher() -> None:
    """STUB: replaced on Day 3 with the ML team's Watcher agent."""
    logger.info(
        "Watcher agent placeholder — no-op (%s)",
        datetime.now(timezone.utc).isoformat(),
    )


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
