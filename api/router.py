"""Mounted HTTP routers for the BidForge API (proposal surface)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.proposal.router import router as proposal_router


def build_proposal_router() -> APIRouter:
    """Proposal routes as mounted under `/api/proposal` in `app.main`."""
    return proposal_router
