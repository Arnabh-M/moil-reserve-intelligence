"""Read-only client-config endpoints — values the frontend needs to mirror
rather than hardcode a second copy of (Field Intake Hardening §5.1).
"""

from fastapi import APIRouter

from app.routers.reports import ALLOWED_UPLOAD_MIME, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/upload-limits", summary="Get the survey-report upload limits")
def get_upload_limits() -> dict:
    """The single source of truth for `POST /reports/upload`'s size/type
    limits, so the Geology tab's dropzone copy and client-side check never
    drift from what the server actually enforces.
    """
    return {"max_report_bytes": MAX_UPLOAD_BYTES, "allowed_mime": ALLOWED_UPLOAD_MIME}
