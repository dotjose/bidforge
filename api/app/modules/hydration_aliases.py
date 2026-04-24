"""Stable top-level GET paths for client hydration (identity from Bearer token, never query user_id)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.contracts.errors import ErrorResponse
from app.core.auth import CurrentUser, get_current_user
from app.modules.proposal.router import ProposalRunSummaryOut, build_proposal_run_summaries
from app.modules.workspace.router import WorkspaceSettingsResponse, build_workspace_settings_response

router = APIRouter(tags=["hydration"])


@router.get(
    "/proposals",
    response_model=list[ProposalRunSummaryOut],
    summary="List saved proposal runs (alias of /api/proposal/runs)",
    responses={401: {"model": ErrorResponse}},
)
async def list_proposals_hydration(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ProposalRunSummaryOut]:
    return build_proposal_run_summaries(user.user_id, limit=50)


@router.get(
    "/settings",
    response_model=WorkspaceSettingsResponse,
    summary="Workspace settings (alias of /api/workspace/settings)",
    responses={401: {"model": ErrorResponse}},
)
async def get_settings_hydration(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> WorkspaceSettingsResponse:
    return build_workspace_settings_response(user.user_id)
