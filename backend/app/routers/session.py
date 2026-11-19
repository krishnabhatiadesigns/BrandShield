"""Session and health endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response

from ..auth import Principal, create_demo_session, get_principal, revoke_demo_session
from ..config import get_settings
from ..db import Database, get_db
from ..models import DemoSessionRequest, MeResponse, SessionResponse

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/demo/session", response_model=SessionResponse)
def demo_session(
    payload: DemoSessionRequest, db: Database = Depends(get_db)
) -> SessionResponse:
    """Enter the pre-seeded demo workspace instantly. No sign-in required."""
    data = create_demo_session(db, payload.role)
    return SessionResponse(**data)


@router.post("/logout", status_code=204)
def logout(
    authorization: str | None = Header(default=None),
    x_demo_token: str | None = Header(default=None),
    db: Database = Depends(get_db),
) -> Response:
    revoke_demo_session(db, authorization, x_demo_token)
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse)
def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        display_name=principal.display_name,
        role=principal.role,  # type: ignore[arg-type]
        workspace_id=principal.workspace_id,
        workspace_name=principal.workspace_name,
        is_demo=principal.is_demo,
        llm_enabled=get_settings().llm_enabled,
    )
