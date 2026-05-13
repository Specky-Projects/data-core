from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from api.routes import router as api_router
from api.poupi_baby_routes import router as poupi_baby_router
from api.schemas import HealthResponse
from core.config import settings
from database.models import Base
from database.session import SessionLocal, engine
from logs.config import configure_logging
from scheduler.service import create_scheduler, start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    scheduler = create_scheduler()
    app.state.scheduler = scheduler
    start_scheduler(scheduler)
    try:
        yield
    finally:
        stop_scheduler(scheduler)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)

    app.include_router(api_router)
    app.include_router(poupi_baby_router)
    return app
