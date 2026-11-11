from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

@router.get("/db", response_model=DatabaseHealthResponse)
def database_health(session: Annotated[Session, Depends(get_session)]) -> DatabaseHealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Never return connection strings or driver errors to API clients.
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return DatabaseHealthResponse()