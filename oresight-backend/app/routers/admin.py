"""Admin/ops route for observing the background scheduler during the demo."""

from fastapi import APIRouter

from app.schemas import JobStatusOut
from app.services.scheduler import get_jobs_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/jobs",
    response_model=list[JobStatusOut],
    summary="List background scheduler jobs and their status",
)
def list_jobs() -> list[JobStatusOut]:
    """Return each registered scheduler job's id, next run time, and last run
    status — proof the ingestion scheduler is alive during the demo.
    """
    return [JobStatusOut(**job) for job in get_jobs_status()]
