"""Server-side PDF export — structured proposal only (no raw RFP, no memory dumps)."""

from __future__ import annotations

import re
from typing import Any, Literal

from fpdf import FPDF
from fpdf.enums import Align, WrapMode, XPos, YPos


def _safe_txt(s: str, limit: int) -> str:
    t = (s or "").replace("\r\n", "\n").strip()
    if len(t) > limit:
        return t[: limit - 3] + "..."
    return t


def _break_long_words(s: str, max_run: int = 88) -> str:
    """Insert spaces into very long unbroken runs so WORD wrap can never exhaust width."""
    lines_out: list[str] = []
    for line in s.split("\n"):
        parts: list[str] = []
        for token in re.split(r"(\s+)", line):
            if not token:
                continue
            if token.isspace():
                parts.append(token)
            elif len(token) <= max_run:
                parts.append(token)
            else:
                parts.append(" ".join(token[i : i + max_run] for i in range(0, len(token), max_run)))
        lines_out.append("".join(parts))
    return "\n".join(lines_out)


def _pdf_text(s: str) -> str:
    """FPDF core fonts are latin-1; replace unsupported chars."""
    return (s or "").encode("latin-1", errors="replace").decode("latin-1")


def _printable_width(pdf: FPDF) -> float:
    """Always use explicit width; never rely on w=0 with a stale x from a prior cell."""
    return max(pdf.epw, 40.0)


def _clean_risk_line(s: str) -> str:
    t = (s or "").strip()
    low = t.lower()
    for prefix in ("freelance_fail:", "missing_requirement:", "compliance_risk:", "weak_claim:"):
        if low.startswith(prefix):
            return t[len(prefix) :].strip()
    return t


def build_proposal_pdf_bytes(
    *,
    title: str,
    sections: dict[str, str],
    timeline: list[dict[str, Any]],
    pipeline_mode: Literal["enterprise", "freelance"] = "enterprise",
    score: int | None = None,
    issues: list[str] | None = None,
    memory_insight_bullets: list[str] | None = None,
    memory_appendix: str | None = None,
) -> bytes:
    """Export client-ready PDF: title, summary, approach, timeline, risks — no raw RFP or memory appendix."""
    _ = memory_appendix
    _ = memory_insight_bullets
    _ = score
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    w = _printable_width(pdf)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(
        w,
        9,
        _pdf_text(_safe_txt(title, 200)),
        align=Align.L,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        wrapmode=WrapMode.WORD,
    )
    pdf.ln(2)

    ex = (sections.get("executive_summary") or "").strip()
    ta = (sections.get("technical_approach") or "").strip()
    dp = (sections.get("delivery_plan") or "").strip()
    rm = (sections.get("risk_management") or "").strip()

    if pipeline_mode == "freelance":
        technical_merged = "\n\n".join(p for p in (ta, dp, rm) if p)
        order = [
            ("Executive summary", ex),
            ("Technical approach", technical_merged),
        ]
    else:
        technical_merged = "\n\n".join(p for p in (ta, dp) if p)
        order = [
            ("Executive summary", ex),
            ("Technical approach", technical_merged),
        ]

    for head, body in order:
        if not body.strip():
            continue
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            w,
            7,
            _pdf_text(head),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.WORD,
        )
        pdf.set_font("Helvetica", size=10)
        body_txt = _pdf_text(_break_long_words(_safe_txt(body, 14_000)))
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            w,
            5,
            body_txt,
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.CHAR,
        )
        pdf.ln(3)

    if timeline:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            w,
            7,
            _pdf_text("Timeline"),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.WORD,
        )
        pdf.set_font("Helvetica", size=10)
        for row in timeline[:40]:
            ph = str(row.get("phase") or "").strip()
            dur = str(row.get("duration") or "").strip()
            line = f"- {ph}" + (f" — {dur}" if dur else "")
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                w,
                5,
                _pdf_text(_safe_txt(line, 500)),
                align=Align.L,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                wrapmode=WrapMode.WORD,
            )
        pdf.ln(2)

    risk_chunks: list[str] = []
    if pipeline_mode == "enterprise" and rm:
        risk_chunks.append(rm)
    for i in issues or []:
        if isinstance(i, str) and i.strip():
            c = _clean_risk_line(i)
            if c:
                risk_chunks.append(c)
    risks_body = "\n\n".join(dict.fromkeys(risk_chunks))[:14_000]

    if risks_body.strip():
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            w,
            7,
            _pdf_text("Risks"),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.WORD,
        )
        pdf.set_font("Helvetica", size=10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            w,
            5,
            _pdf_text(_break_long_words(_safe_txt(risks_body, 14_000))),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.CHAR,
        )

    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1", errors="replace")
