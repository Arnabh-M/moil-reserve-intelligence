"""POST /reports/upload — survey PDF in, structured deposits out, plus the
matching OreZone / StructuralFeature nodes MERGE-d into Neo4j.

Pipeline: multipart PDF -> pypdf text -> DepositExtractor (deterministic
today, LLM-swappable — see app.services.extraction) -> Neo4j MERGE. Every
stage degrades to a clean response instead of a 500:
  - unreadable / text-less PDF  -> 200, text_extracted=false, deposits=[]
  - nothing matched by the parser -> 200, deposits=[]
  - Neo4j unavailable            -> 200, nodes_created=[], warning added
Only a genuinely bad request (not a PDF, empty, oversized) is a 4xx.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from neo4j import Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.graph_db import get_graph_driver
from app.schemas import GraphNode, ReportUploadOut
from app.schemas.report import ExtractedDeposit
from app.services.extraction import get_extractor
from app.services.pdf_text import extract_pdf_text

logger = logging.getLogger("oresight.reports")

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — survey PDFs are text, not imagery


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "x"


def _match_site(belt_zone: str | None, sites: list[dict]) -> str | None:
    """Map an extracted belt/zone string to a Neo4j MineSite.id.

    Prefers a hit on the site's own name/id (unambiguous) over its
    belt_name (which two sites share). Returns None when nothing matches or
    the only match is an ambiguous shared belt.
    """
    if not belt_zone:
        return None
    hay = belt_zone.lower()

    for s in sites:
        if s["id"].lower() in hay or (s.get("name") and s["name"].lower().split()[0] in hay):
            return s["id"]

    belt_hits = [s for s in sites if s.get("belt_name") and s["belt_name"].lower() in hay]
    if len(belt_hits) == 1:
        return belt_hits[0]["id"]
    return None


def _write_graph(
    driver: Driver, deposits: list[ExtractedDeposit]
) -> tuple[list[GraphNode], list[str]]:
    """MERGE an OreZone (and StructuralFeature, when known) per deposit, plus
    LOCATED_IN edges to the matched MineSite. Idempotent on repeated uploads
    of the same deposit_id (MERGE keyed on the derived node id).
    """
    nodes: list[GraphNode] = []
    warnings: list[str] = []

    with driver.session() as session:
        sites = session.run(
            "MATCH (s:MineSite) RETURN s.id AS id, s.name AS name, s.belt_name AS belt_name"
        ).data()

        for d in deposits:
            slug = _slug(d.deposit_id)
            oz_id = f"oz_upload_{slug}"
            site_id = _match_site(d.belt_zone, sites)
            if d.belt_zone and site_id is None:
                warnings.append(
                    f"deposit {d.deposit_id}: belt/zone {d.belt_zone!r} matched no known site "
                    "— nodes created but not linked to a MineSite"
                )

            session.run(
                """
                MERGE (z:OreZone {id: $id})
                SET z.deposit_id = $deposit_id,
                    z.grade_estimate = $grade,
                    z.depth_m = $depth,
                    z.confidence_score = coalesce(z.confidence_score, 0.5),
                    z.source = 'report_upload',
                    z.site_id = coalesce($site_id, z.site_id)
                """,
                id=oz_id, deposit_id=d.deposit_id, grade=d.grade, depth=d.depth, site_id=site_id,
            )
            nodes.append(GraphNode(id=oz_id, label=d.deposit_id, type="OreZone"))

            if site_id is not None:
                session.run(
                    "MATCH (z:OreZone {id: $id}), (s:MineSite {id: $site_id}) "
                    "MERGE (z)-[:LOCATED_IN]->(s)",
                    id=oz_id, site_id=site_id,
                )

            if d.structure_type:
                sf_id = f"sf_upload_{slug}"
                session.run(
                    """
                    MERGE (f:StructuralFeature {id: $id})
                    SET f.feature_type = $feature_type,
                        f.deposit_id = $deposit_id,
                        f.density_score = coalesce(f.density_score, 0.5),
                        f.source = 'report_upload',
                        f.site_id = coalesce($site_id, f.site_id)
                    """,
                    id=sf_id, feature_type=d.structure_type, deposit_id=d.deposit_id, site_id=site_id,
                )
                nodes.append(
                    GraphNode(id=sf_id, label=f"{d.structure_type} ({d.deposit_id})", type="StructuralFeature")
                )
                if site_id is not None:
                    session.run(
                        "MATCH (f:StructuralFeature {id: $id}), (s:MineSite {id: $site_id}) "
                        "MERGE (f)-[:LOCATED_IN]->(s)",
                        id=sf_id, site_id=site_id,
                    )

    return nodes, warnings


@router.post("/upload", response_model=ReportUploadOut, summary="Upload a survey PDF for extraction")
async def upload_report(
    file: UploadFile = File(..., description="A geological survey report, PDF"),
    driver: Driver = Depends(get_graph_driver),
) -> ReportUploadOut:
    """Extract deposit entities from a survey PDF and MERGE them into the graph.

    - Not a PDF / empty / larger than 10 MB -> 400.
    - PDF with no extractable text -> 200 with `text_extracted=false`, `deposits=[]`.
    - Parser finds nothing -> 200 with `deposits=[]`.
    - Neo4j unavailable -> 200 with `nodes_created=[]` and a warning; the
      extracted deposits are still returned so the frontend can show them.
    """
    filename = file.filename or "upload.pdf"
    content_type = (file.content_type or "").lower()
    if "pdf" not in content_type and not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Expected a PDF upload; got content-type {content_type or 'unknown'!r} / {filename!r}.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File is {len(data) // 1024} KB; limit is {MAX_UPLOAD_BYTES // 1024} KB.",
        )

    text = extract_pdf_text(data)
    if not text:
        return ReportUploadOut(
            filename=filename,
            text_extracted=False,
            deposit_count=0,
            deposits=[],
            nodes_created=[],
            warnings=["No extractable text found in the uploaded PDF (it may be scanned images or empty)."],
        )

    deposits = get_extractor().extract(text)

    warnings: list[str] = []
    nodes: list[GraphNode] = []
    if deposits:
        try:
            nodes, warnings = _write_graph(driver, deposits)
        except (ServiceUnavailable, Neo4jError, OSError) as exc:
            logger.warning("Neo4j write failed during report upload: %s", exc)
            warnings = [
                "Graph store (Neo4j) unavailable — extracted deposits were not persisted to the graph."
            ]
    else:
        warnings.append("No deposit entities could be extracted from the report text.")

    return ReportUploadOut(
        filename=filename,
        text_extracted=True,
        deposit_count=len(deposits),
        deposits=deposits,
        nodes_created=nodes,
        warnings=warnings,
    )
