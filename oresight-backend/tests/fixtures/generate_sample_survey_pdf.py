"""Regenerate tests/fixtures/sample_survey.pdf — a realistic MOIL-style
geological survey report used by tests/test_reports.py.

The generated PDF is committed, so the test suite does NOT need fpdf2. Only
run this when you want to change the fixture content:

    pip install fpdf2
    python tests/fixtures/generate_sample_survey_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).with_name("sample_survey.pdf")

BODY = """MOIL LIMITED
GEOLOGICAL EXPLORATION REPORT - Q3 2026

Site: Balaghat Mine
Belt: Balaghat-Manganese Belt
Survey party: GSI-MOIL joint exploration cell
Report ref: MOIL/BAL/EXPL/2026-07

1. SUMMARY

Three exploratory boreholes were completed in the Balaghat North and East
blocks during this quarter. Manganese ore intersections were logged in all
three. Grades are reported as average Mn percent over the mineralised
interval. Structural context is summarised per deposit below.
All co-ordinates omitted from this extract.

2. DEPOSIT LOGS

Deposit BAL-D1
  Borehole depth: 145.2 m
  Average Mn grade: 38.5 %
  Dominant structure: tight fold axis, NE-SW trending
  Host rock: gondite, moderately weathered to 40 m
  Remarks: ore body conformable with fold limb; strike continuity good.

Deposit BAL-D2
  Drilled depth of 98 m
  Grade: 24.1% Mn
  Structure: cross-cutting fault line offsets the ore horizon by about 6 m
  Remarks: footwall block down-thrown; second intercept expected deeper.

Deposit BAL-D3
  Final depth 172.0 metres
  Mn 31.7 %
  Structural setting: broad shear zone with chlorite alteration
  Remarks: disseminated braunite; grade lower at margins.

3. RECOMMENDATIONS

Extend BAL-D2 to 140 m in the next campaign. Re-survey the BAL-D1 fold
closure with closer-spaced holes.
"""


def main() -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    epw = pdf.w - pdf.l_margin - pdf.r_margin
    for line in BODY.split("\n"):
        if line.strip():
            pdf.multi_cell(epw, 6, line)
        else:
            pdf.ln(6)
    pdf.output(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
