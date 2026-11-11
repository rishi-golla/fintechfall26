from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings

def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
def get_session(request: Request) -> Iterator[Session]:
    # Callers explicitly commit writes; closing rolls back unfinished transactions.
    with request.app.state.session_factory() as session:
        yield session