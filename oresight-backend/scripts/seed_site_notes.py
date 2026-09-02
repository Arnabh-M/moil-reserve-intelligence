"""Seed realistic MOIL-style field notes into site_notes, with embeddings,
so GET /site-notes/search returns something meaningful in the demo.

Idempotent: a note is matched on (site_id, exact text). New notes are
inserted; existing ones have their embedding recomputed in place, so a
re-run after the embedder changes refreshes the vectors without creating
duplicates.

Run from oresight-backend/ (after `alembic upgrade head` and app.seed_dev):
    python -m scripts.seed_site_notes
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Site, SiteNote  # noqa: E402
from app.services.embedding import get_embedder  # noqa: E402

# district (lowercased) -> notes
NOTES: dict[str, list[str]] = {
    "balaghat": [
        "North Block face 3 is showing higher braunite content than the 2024 block model predicted; grade-check samples sent to the Nagpur lab for assay.",
        "Monsoon runoff pooling at the base of the western ramp after two days of heavy rain; dewatering pumps running double shift to keep the haul road passable.",
        "Drill BAL-1 back in service after a hydraulic hose replacement; roughly six hours lost on bench 7 waiting for the part.",
        "The fold closure in the East Block is tighter than mapped - blast crew advised to cut the burden on the next round to avoid overbreak.",
        "Community liaison meeting flagged dust complaints along the Katangi approach road; water-tanker frequency increased to four passes a shift.",
    ],
    "nagpur": [
        "Excavator NAG-1 hydraulic fault recurred on the day shift; arranging a standby machine from Bhandara while the pump is rebuilt.",
        "Shear zone on the south wall is weeping groundwater after the last rain; geotech watching for a wedge failure and has flagged the bench for survey.",
        "Rail rake availability from the railway is down this week - the ore stockpile at the siding is close to capacity.",
        "Low-grade dilution is creeping up on bench 4; mucking crew reminded to respect the ore/waste paint line and re-mark it each round.",
        "Night-shift blast postponed once for a lightning warning; explosive magazine inventory reconciled with no discrepancy.",
    ],
    "bhandara": [
        "Conveyor BHD-1 belt splice is holding after last month's repair; vibration readings on the drive pulley are back to normal.",
        "The fault line near the pit boundary offsets the ore horizon by about five metres, down-thrown to the east - second intercept expected deeper.",
        "Exploration borehole BHD-EX2 drilled to 150 m depth intercepted a 31 percent manganese grade over four metres - encouraging for the deeper reserve block.",
        "Access-road culvert washed out after overnight rain; a single-lane diversion is in place and the repair is scheduled for the weekend.",
        "Compressor BHD-1 tripped on high coolant temperature twice this week; radiator flushed and the unit is under watch.",
    ],
}


def main() -> None:
    db = SessionLocal()
    embedder = get_embedder()
    try:
        created = refreshed = 0
        for district, texts in NOTES.items():
            site = db.scalar(select(Site).where(Site.district.ilike(district)))
            if site is None:
                print(f"  WARN: no site with district ~ {district!r}; skipping its notes")
                continue
            for text in texts:
                vec = embedder.embed(text)
                existing = db.scalar(
                    select(SiteNote).where(
                        SiteNote.site_id == site.id, SiteNote.text == text
                    )
                )
                if existing is not None:
                    existing.embedding = vec
                    refreshed += 1
                else:
                    db.add(SiteNote(site_id=site.id, text=text, embedding=vec))
                    created += 1
        db.commit()
        print(f"site_notes seed: {created} created, {refreshed} embedding(s) refreshed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
