"""Binary → plain text for PDF, DOCX, and URL ingestion."""

from __future__ import annotations

import io
import logging
import re
from typing import Final

import httpx

log = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    t = _HTML_TAG_RE.sub(" ", html)
    t = re.sub(r"(?i)<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.DOTALL)
    return _WS_RE.sub(" ", t).strip()


def extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        log.warning("pypdf not installed")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        parts: list[str] = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                t = ""
            if t.strip():
                parts.append(t.strip())
        return "\n\n".join(parts).strip()
    except Exception as e:  # noqa: BLE001
        log.warning("pdf extract failed: %s", e)
        return ""


def extract_docx_text(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        log.warning("python-docx not installed")
        return ""
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    except Exception as e:  # noqa: BLE001
        log.warning("docx extract failed: %s", e)
        return ""


_MAX_URL_BYTES: Final[int] = 12_000_000


def fetch_url_bytes(url: str, *, timeout_s: float = 30.0) -> tuple[bytes, str | None]:
    with httpx.Client(follow_redirects=True, timeout=timeout_s) as client:
        r = client.get(url, headers={"User-Agent": "BidForgeDocumentFetcher/1.0"})
        r.raise_for_status()
        ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
        data = r.content
        if len(data) > _MAX_URL_BYTES:
            raise ValueError("response too large")
        return data, ct


def extract_from_url(url: str) -> tuple[str, str]:
    """Return (plain_text, inferred_source) where inferred_source is pdf|text."""
    data, ct = fetch_url_bytes(url)
    if "pdf" in ct or url.lower().endswith(".pdf"):
        txt = extract_pdf_text(data)
        return txt, "pdf"
    if ct in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) or url.lower().endswith(
        ".docx"
    ):
        return extract_docx_text(data), "docx"
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    if "text/html" in ct or "<html" in text[:2000].lower():
        return _strip_html(text), "text"
    return text.strip(), "text"
