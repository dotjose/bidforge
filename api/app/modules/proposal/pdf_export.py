"""Server-side PDF export — structured proposal only (no raw RFP, no memory dumps)."""

from __future__ import annotations

import re
import unicodedata
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


def _strip_light_markdown(s: str) -> str:
    """Remove common markdown tokens — PDF uses plain text, not a markdown renderer."""
    t = s or ""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t, flags=re.DOTALL)
    t = re.sub(r"__(.+?)__", r"\1", t, flags=re.DOTALL)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"^#+\s+", "", t, flags=re.MULTILINE)
    return t


def _normalize_for_pdf_core_fonts(s: str) -> str:
    """
    Core PDF fonts are limited to Latin-1. Map bullets / punctuation / symbols to ASCII
    before latin-1 encoding so lists render as '-' instead of '?'.
    """
    t = unicodedata.normalize("NFKC", s or "")
    repl = {
        "\u2022": "- ",  # bullet
        "\u2023": "- ",
        "\u2043": "- ",
        "\u2219": "- ",
        "\u25aa": "- ",
        "\u25cf": "- ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": "",
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    # Strip emoji / non-latin-1 remainder (no hallucinated glyphs)
    out: list[str] = []
    for ch in t:
        o = ord(ch)
        if ch == "\n" or ch == "\t":
            out.append(ch)
        elif o < 128:
            out.append(ch)
        elif o <= 255:
            try:
                ch.encode("latin-1")
                out.append(ch)
            except UnicodeEncodeError:
                out.append(" ")
        else:
            out.append(" ")
    return "".join(out)


def _pdf_text(s: str) -> str:
    """Core-font safe line — bullets and common unicode normalized first."""
    step = _strip_light_markdown(_normalize_for_pdf_core_fonts(s))
    return step.encode("latin-1", errors="replace").decode("latin-1")


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
    """Export client-ready PDF: title, summary, approach, timeline, risks — no raw RFP or memory dumps."""
    _ = memory_appendix
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

    ex = (sections.get("opening") or sections.get("hook") or sections.get("executive_summary") or "").strip()
    what = (sections.get("understanding") or sections.get("what_ill_deliver") or "").strip()
    sol = (sections.get("solution") or "").strip()
    ta = (sections.get("execution_plan") or sections.get("technical_approach") or "").strip()
    tl = (sections.get("timeline") or sections.get("timeline_block") or "").strip()
    deliv = (sections.get("deliverables") or sections.get("deliverables_block") or "").strip()
    dp = (sections.get("delivery_plan") or "").strip()
    rel = (sections.get("experience") or sections.get("relevant_experience") or "").strip()
    risk_r = (sections.get("risks") or sections.get("risk_reduction") or "").strip()
    rm = (sections.get("risk_management") or "").strip()
    cta = (sections.get("next_step") or sections.get("call_to_action") or "").strip()

    if pipeline_mode == "freelance":
        body_merged = "\n\n".join(p for p in (what, sol, ta, tl, deliv, dp, rel, risk_r, rm, cta) if p)
        order = [
            ("Opening", ex),
            ("Proposal", body_merged),
        ]
    elif what or sol or ta or tl or deliv:
        order = [
            ("Opening", ex),
            ("Understanding", what),
            ("Solution", sol),
            ("Execution plan", ta),
            ("Timeline", tl),
            ("Deliverables", deliv),
            ("Relevant experience", rel),
            ("Risk management", risk_r or rm[:4000] if rm else ""),
            ("Next step", cta),
        ]
    else:
        technical_merged = "\n\n".join(p for p in (ta, dp, rm) if p)
        order = [
            ("Opening", ex),
            ("Plan & proof", technical_merged),
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

    bullets = [str(b).strip() for b in (memory_insight_bullets or []) if str(b).strip()]
    if bullets:
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            w,
            7,
            _pdf_text("Memory-informed signals"),
            align=Align.L,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.WORD,
        )
        pdf.set_font("Helvetica", size=10)
        for b in bullets[:24]:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                w,
                5,
                _pdf_text(f"- {_safe_txt(b, 400)}"),
                align=Align.L,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                wrapmode=WrapMode.WORD,
            )

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
