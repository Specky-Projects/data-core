from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from api.routes import router as api_router
from api.poupi_baby_routes import router as poupi_baby_router
from api.schemas import HealthResponse
from app.analytics import models as analytics_models
from app.data_quality import models as data_quality_models
from app.data_quality.api import router as data_quality_router
from app.documentation import models as documentation_models
from app.documentation.api import router as documentation_router
from app.modules.real_estate.api import router as real_estate_router
from app.modules.real_estate import models as real_estate_models
from app.modules.registry import register_pipeline_modules
from app.modules.sports_odds.api import router as sports_odds_router
from app.modules.sports_odds import models as sports_odds_models
from app.normalization import models as normalization_models
from app.raw import models as raw_models
from app.pipeline_api import router as pipeline_router
from core.config import settings
from database.models import Base
from database.session import SessionLocal, engine
from logs.config import configure_logging
from scheduler.service import create_scheduler, start_scheduler, stop_scheduler

_ = real_estate_models
_ = sports_odds_models
_ = raw_models
_ = normalization_models
_ = analytics_models
_ = data_quality_models
_ = documentation_models


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        app.state.scheduler = scheduler
        start_scheduler(scheduler)
    try:
        yield
    finally:
        if scheduler is not None:
            stop_scheduler(scheduler)


def create_app() -> FastAPI:
    register_pipeline_modules()
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
    app.include_router(pipeline_router)
    app.include_router(documentation_router)
    app.include_router(data_quality_router)
    app.include_router(real_estate_router)
    app.include_router(sports_odds_router)
    return app
