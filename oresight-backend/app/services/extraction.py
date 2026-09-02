"""Deposit extraction: survey text in, structured `ExtractedDeposit`s out.

DESIGN — one seam, deliberately narrow
-------------------------------------
`DepositExtractor.extract(text) -> list[ExtractedDeposit]` is the *only*
contract. The route (app.routers.reports) and the Neo4j write path depend
on that signature and the `ExtractedDeposit` shape, nothing else.

The default implementation, `RegexDepositExtractor`, is fully deterministic
— no network, no API key, no model. An LLM-backed implementation can be
dropped in later by writing another class with the same `.extract()` and
changing `get_extractor()`; nothing else in the codebase should need to
change. Keep any such implementation's output to exactly `ExtractedDeposit`
(five fields) — do not let it leak provider-specific extras upward.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from app.schemas.report import ExtractedDeposit

logger = logging.getLogger("oresight.reports")


# --- structure-type canonicalisation -------------------------------------------------
# Free-text geology terms -> the underscored vocabulary seed_graph.cypher uses
# for StructuralFeature.feature_type (fold_axis / fault_line / shear_zone …).
_STRUCTURE_CANON: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bfold(\s*axis|ing)?\b", re.I), "fold_axis"),
    (re.compile(r"\b(fault(\s*line|ing)?|faulted)\b", re.I), "fault_line"),
    (re.compile(r"\bshear(\s*zone)?\b", re.I), "shear_zone"),
    (re.compile(r"\b(fracture|fractured|joint(ing|ed)?)\b", re.I), "fracture_zone"),
    (re.compile(r"\b(bedding|bedded|strata(form)?)\b", re.I), "bedding_plane"),
    (re.compile(r"\b(contact|intrusive\s*contact)\b", re.I), "contact_zone"),
]

# A deposit block starts at one of these headers. Group `id` is the deposit
# id — any dash/underscore/slash-joined alphanumeric token that contains at
# least one digit (so "BAL-D1", "HT-302", "bp_bal_01" match but "LOGS" doesn't).
_DEPOSIT_HEADER = re.compile(
    r"""^[ \t]*
        (?:deposit|block|lode|prospect|borehole|bore\s*hole|drill\s*hole)\b
        [ \t]*(?:id|no\.?|number|ref)?[ \t]*[:\-#]?[ \t]*
        (?P<id>(?=[A-Za-z0-9/_-]*\d)[A-Za-z0-9][A-Za-z0-9/_-]{1,24})
    """,
    re.I | re.X | re.M,
)

_DEPTH_RE = re.compile(
    r"""(?:borehole\s*|drill(?:ed)?\s*|final\s*|total\s*|deposit\s*)?
        depth\s*(?:of|:|=)?\s*
        (?P<val>\d{1,4}(?:\.\d{1,2})?)\s*
        (?P<unit>m\b|metre?s?\b|meter?s?\b)
    """,
    re.I | re.X,
)
# also catch "intersected at 145.2 m" / "145.2 m below surface"
_DEPTH_RE_ALT = re.compile(
    r"(?:intersected|encountered|struck)\s+(?:at\s+)?(?P<val>\d{1,4}(?:\.\d{1,2})?)\s*m\b",
    re.I,
)

_GRADE_RE = re.compile(
    r"""(?:average\s*|avg\.?\s*|mean\s*|est(?:imated)?\.?\s*|Mn\s*)?
        grade\s*(?:of|:|=)?\s*
        (?P<val>\d{1,3}(?:\.\d{1,2})?)\s*
        (?:%|percent|pct)?\s*(?:Mn)?
    """,
    re.I | re.X,
)
# also catch "38.5% Mn" / "Mn 38.5 %" without the word "grade"
_GRADE_RE_ALT = re.compile(
    r"(?:Mn\s*[:=]?\s*(?P<v1>\d{1,3}(?:\.\d{1,2})?)\s*%?)"
    r"|(?:(?P<v2>\d{1,3}(?:\.\d{1,2})?)\s*%\s*Mn\b)",
    re.I,
)

_STRUCTURE_LINE_RE = re.compile(
    r"(?:dominant|primary|main|host|local|regional)?\s*"
    r"structur(?:e|al)(?:\s*(?:type|setting|context|style|regime|control))?"
    r"\s*(?:of|:|=|is|-)?\s*(?P<val>[A-Za-z][A-Za-z \-]{2,50})",
    re.I,
)

# "<name> Belt: …" / "Belt: <name>" (name after the keyword)
_BELT_RE = re.compile(
    r"(?:manganese\s+)?belt(?:\s*zone)?\s*(?:of|:|=)\s*(?P<val>[A-Za-z][A-Za-z0-9 \-]{3,60})",
    re.I,
)
# "<name> Manganese Belt" (name before the keyword — very common in MOIL reports)
_BELT_RE_ALT = re.compile(
    r"(?P<val>[A-Za-z][A-Za-z \-]{3,45}?\s+(?:manganese\s+)?belt)\b", re.I
)
# document-level "Site: Balaghat Mine" as a belt-zone fallback
_SITE_RE = re.compile(r"^\s*(?:site|mine|location)\s*[:\-]\s*(?P<val>[A-Za-z][A-Za-z \-]{2,40})", re.I | re.M)

# A numbered or all-caps section heading — the end of the last deposit block.
_SECTION_HEADING_RE = re.compile(r"^[ \t]*(?:\d+(?:\.\d+)*[.)]\s+\S|[A-Z][A-Z /&-]{4,}\s*$)", re.M)


class DepositExtractor(Protocol):
    def extract(self, text: str) -> list[ExtractedDeposit]: ...


class RegexDepositExtractor:
    """Deterministic parser for MOIL-style geological survey text."""

    def extract(self, text: str) -> list[ExtractedDeposit]:
        if not text or not text.strip():
            return []

        doc_belt = (
            self._first(_BELT_RE, text)
            or self._first(_BELT_RE_ALT, text)
            or self._first(_SITE_RE, text)
        )

        headers = list(_DEPOSIT_HEADER.finditer(text))
        if not headers:
            # No per-deposit structure — treat the whole document as one
            # implicit deposit, but only emit it if we actually found
            # something worth returning.
            single = self._parse_block(text, deposit_id=None, doc_belt=doc_belt)
            return [single] if single is not None else []

        deposits: list[ExtractedDeposit] = []
        for i, header in enumerate(headers):
            block_start = header.end()
            if i + 1 < len(headers):
                block_end = headers[i + 1].start()
            else:
                # last block: stop at the next section heading so trailing
                # prose (recommendations, appendices) doesn't leak in.
                section = _SECTION_HEADING_RE.search(text, block_start)
                block_end = section.start() if section else len(text)
            block = text[block_start:block_end]
            parsed = self._parse_block(
                block, deposit_id=self._clean_id(header.group("id")), doc_belt=doc_belt
            )
            if parsed is not None:
                deposits.append(parsed)

        # De-dupe on deposit_id, first occurrence wins (a survey often repeats
        # the id in a summary table).
        seen: set[str] = set()
        unique: list[ExtractedDeposit] = []
        for d in deposits:
            if d.deposit_id in seen:
                continue
            seen.add(d.deposit_id)
            unique.append(d)
        return unique

    # -- internals -----------------------------------------------------

    def _parse_block(
        self, block: str, deposit_id: str | None, doc_belt: str | None
    ) -> ExtractedDeposit | None:
        depth = self._num(_DEPTH_RE, block, "val") or self._num(_DEPTH_RE_ALT, block, "val")
        grade = self._num(_GRADE_RE, block, "val")
        if grade is None:
            m = _GRADE_RE_ALT.search(block)
            if m:
                raw = m.group("v1") or m.group("v2")
                grade = float(raw) if raw else None

        # Prefer a phrase explicitly labelled as the structure; only fall
        # back to scanning the whole block if there's no such line.
        struct_line = self._first(_STRUCTURE_LINE_RE, block)
        structure_type = self._canon_structure(struct_line) if struct_line else None
        if structure_type is None:
            structure_type = self._canon_structure(block)

        belt_zone = (
            self._first(_BELT_RE, block)
            or self._first(_BELT_RE_ALT, block)
            or doc_belt
        )

        # Guard against absurd parses (e.g. a page number picked up as depth).
        if depth is not None and not (0 < depth <= 3000):
            depth = None
        if grade is not None and not (0 < grade <= 100):
            grade = None

        if deposit_id is None:
            # implicit single-deposit doc: need at least one real signal
            if depth is None and grade is None and structure_type is None:
                return None
            deposit_id = "DEPOSIT-1"

        if depth is None and grade is None and structure_type is None and belt_zone is None:
            # a header with a totally empty body — skip it
            return None

        return ExtractedDeposit(
            deposit_id=deposit_id,
            depth=depth,
            grade=grade,
            structure_type=structure_type,
            belt_zone=belt_zone.strip() if belt_zone else None,
        )

    @staticmethod
    def _clean_id(raw: str) -> str:
        return re.sub(r"\s+", "-", raw.strip()).upper().strip("-_/")

    @staticmethod
    def _first(pattern: re.Pattern[str], text: str) -> str | None:
        m = pattern.search(text)
        return m.group("val").strip() if m else None

    @staticmethod
    def _num(pattern: re.Pattern[str], text: str, group: str) -> float | None:
        m = pattern.search(text)
        if not m:
            return None
        try:
            return float(m.group(group))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _canon_structure(text: str) -> str | None:
        for pattern, canon in _STRUCTURE_CANON:
            if pattern.search(text):
                return canon
        return None


def get_extractor() -> DepositExtractor:
    """Return the active deposit extractor.

    Single swap-point: to move to an LLM-backed extractor, implement one
    with the same `.extract()` signature and return it here.
    """
    return RegexDepositExtractor()
