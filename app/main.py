from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app.api.health import router
from app.core.config import Settings
from app.db.session import build_engine

def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        engine = build_engine(config)
        app.title = config.app_name
        app.state.session_factory = sessionmaker(bind=engine)
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="ClaimForge", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
