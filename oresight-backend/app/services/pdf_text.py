"""PDF -> plain text, isolated behind one function so the route never
touches pypdf directly.

Deliberately forgiving: a corrupt, encrypted, image-only, or zero-page PDF
yields an empty string, never an exception. The caller decides what an
empty extraction means (POST /reports/upload returns a clean empty result,
not a 500).
"""

from __future__ import annotations

import io
import logging
from datetime import date

from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PyPdfError

logger = logging.getLogger("oresight.reports")


class PdfMetadata(BaseModel):
    """Best-effort PDF document-info metadata. Every field is `None` when
    the PDF has no such metadata, is unreadable, or is encrypted — never an
    exception. This is document *properties* (page count, author, creation
    date), not content extraction; the parsed report text still comes from
    `extract_pdf_text`.
    """

    page_count: int | None = None
    author: str | None = None
    report_date: date | None = None


def extract_pdf_metadata(data: bytes) -> PdfMetadata:
    """Return page count + author/creation-date from the PDF's document-info
    dictionary. Degrades to an all-`None` `PdfMetadata` on any failure —
    mirrors `extract_pdf_text`'s "never raise" contract.
    """
    if not data:
        return PdfMetadata()

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PyPdfError, ValueError, OSError) as exc:
        logger.warning("PDF metadata could not be read: %s", exc)
        return PdfMetadata()

    page_count: int | None
    try:
        page_count = len(reader.pages)
    except Exception:  # noqa: BLE001 - page_count is best-effort only
        page_count = None

    author: str | None = None
    report_date: date | None = None
    try:
        info = reader.metadata
        if info is not None:
            author = (info.author or "").strip() or None
            if info.creation_date is not None:
                report_date = info.creation_date.date()
    except Exception as exc:  # noqa: BLE001 - metadata is best-effort only
        logger.warning("PDF document-info metadata could not be read: %s", exc)

    return PdfMetadata(page_count=page_count, author=author, report_date=report_date)


def extract_pdf_text(data: bytes) -> str:
    """Return all extractable text from a PDF byte string.

    Pages whose text can't be decoded are skipped individually rather than
    failing the whole document. Returns "" for anything unreadable.
    """
    if not data:
        return ""

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PyPdfError, ValueError, OSError) as exc:
        logger.warning("PDF could not be parsed: %s", exc)
        return ""

    if reader.is_encrypted:
        # Try the common "empty user password" case; give up quietly otherwise.
        try:
            if reader.decrypt("") == 0:  # 0 == decryption failed
                logger.warning("PDF is encrypted and no password was supplied")
                return ""
        except (NotImplementedError, PyPdfError) as exc:
            logger.warning("PDF decryption unsupported: %s", exc)
            return ""

    chunks: list[str] = []
    for page_num, page in enumerate(reader.pages):
        try:
            chunks.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 - one bad page shouldn't sink the doc
            logger.warning("Page %d text extraction failed: %s", page_num, exc)

    return "\n".join(c for c in chunks if c).strip()
