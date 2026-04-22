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
    """Render proposal body + optional short review summary. Legacy `memory_appendix` is ignored."""
    _ = memory_appendix
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

    if pipeline_mode == "freelance":
        order = [
            ("Hook", sections.get("executive_summary") or ""),
            ("Understanding of your need", sections.get("technical_approach") or ""),
            ("Approach & relevant experience", sections.get("delivery_plan") or ""),
            ("Call to action", sections.get("risk_management") or ""),
        ]
    else:
        order = [
            ("Executive summary", sections.get("executive_summary") or ""),
            ("Technical approach", sections.get("technical_approach") or ""),
            ("Delivery plan", sections.get("delivery_plan") or ""),
            ("Risk management", sections.get("risk_management") or ""),
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

    bullets = [b.strip() for b in (memory_insight_bullets or []) if isinstance(b, str) and b.strip()][:8]
    issue_lines = [i.strip() for i in (issues or []) if isinstance(i, str) and i.strip()][:12]
    if score is not None or issue_lines or bullets:
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            w,
            7,
            _pdf_text("Review summary"),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.WORD,
        )
        pdf.set_font("Helvetica", size=10)
        if score is not None:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                w,
                5,
                _pdf_text(f"Verifier score: {int(score)}/100"),
                align=Align.L,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                wrapmode=WrapMode.WORD,
            )
        if issue_lines:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                w,
                5,
                _pdf_text("Top issues:"),
                align=Align.L,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                wrapmode=WrapMode.WORD,
            )
            for line in issue_lines:
                pdf.set_x(pdf.l_margin + 4)
                pdf.multi_cell(
                    w - 4,
                    5,
                    _pdf_text(f"- {_safe_txt(line, 400)}"),
                    align=Align.L,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    wrapmode=WrapMode.WORD,
                )
        if bullets:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                w,
                5,
                _pdf_text("Win-pattern signals used:"),
                align=Align.L,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                wrapmode=WrapMode.WORD,
            )
            for b in bullets:
                pdf.set_x(pdf.l_margin + 4)
                pdf.multi_cell(
                    w - 4,
                    5,
                    _pdf_text(f"- {_safe_txt(b, 320)}"),
                    align=Align.L,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    wrapmode=WrapMode.WORD,
                )

    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1", errors="replace")
