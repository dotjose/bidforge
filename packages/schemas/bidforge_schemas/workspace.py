"""Canonical workspace contracts — stateful bid OS (agents consume WorkspaceState, not raw UI)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

InputSource = Literal["text", "pdf", "docx", "url"]


class NormalizedSection(BaseModel):
    name: str = Field(default="", max_length=512)
    content: str = Field(default="", max_length=200_000)


class NormalizedDocumentMetadata(BaseModel):
    client: str = ""
    deadline: str = ""
    budget: str = ""
    job_type_hint: str = Field(
        default="",
        description="Lightweight hint from filename/headers (e.g. upwork, enterprise_rfp).",
    )


class NormalizedDocumentOutput(BaseModel):
    """DocumentNormalizerAgent structured output."""

    title: str = Field(default="", max_length=512)
    sections: list[NormalizedSection] = Field(default_factory=list)
    metadata: NormalizedDocumentMetadata = Field(default_factory=NormalizedDocumentMetadata)


class WorkspaceRfp(BaseModel):
    """Normalized brief inside the workspace."""

    source: InputSource = "text"
    title: str = ""
    sections: list[NormalizedSection] = Field(default_factory=list)
    body: str = Field(
        default="",
        description="Flattened plain text used for deterministic extraction (no UI labels).",
    )


class RagConfig(BaseModel):
    """Per-workspace RAG toggles — never global."""

    enabled: bool = True
    enterprise_case_studies: bool = True
    freelance_win_memory: bool = True


class WorkspaceSettings(BaseModel):
    tone: str = ""
    writing_style: str = ""
    proposal_mode: Literal["auto", "enterprise", "freelance"] = "auto"
    rag: RagConfig = Field(default_factory=RagConfig)
    company_profile: dict[str, Any] = Field(
        default_factory=dict,
        description="company_name, services, strengths, methodology mirrors profiles table.",
    )


class WorkspaceMemory(BaseModel):
    """Echo / scratch for retrieval — filled during RAGRetriever step."""

    rag_context_summary: dict[str, Any] = Field(default_factory=dict)
    last_retrieval_mode: str = ""


class WorkspaceProposal(BaseModel):
    """Populated after proposal stages — UI sync uses API envelope + this slice."""

    status: str = "idle"
    score: int | None = None


class WorkspaceState(BaseModel):
    """Single canonical object for the bid workspace."""

    user_id: str = ""
    trace_id: str = ""
    rfp: WorkspaceRfp = Field(default_factory=WorkspaceRfp)
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    memory: WorkspaceMemory = Field(default_factory=WorkspaceMemory)
    proposal: WorkspaceProposal = Field(default_factory=WorkspaceProposal)
