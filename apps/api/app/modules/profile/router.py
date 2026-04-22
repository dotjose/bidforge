from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me")
async def profile_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    return {"user_id": user.user_id, "email": user.email}
