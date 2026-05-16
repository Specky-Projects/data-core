from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from api.auth import verify_api_key
from api.rate_limit import limiter
from api.routes import router as api_router
from api.poupi_baby_routes import router as poupi_baby_router
from api.schemas import DependencyStatus, HealthResponse
from app.analytics import models as analytics_models
from app.data_quality import models as data_quality_models
from app.data_quality.api import router as data_quality_router
from app.documentation import models as documentation_models
from app.documentation.api import router as documentation_router
from app.middleware.correlation import CorrelationMiddleware
from app.modules.crypto.api import router as crypto_router
from app.modules.real_estate.api import router as real_estate_router
from app.modules.real_estate import models as real_estate_models
from app.modules.registry import register_pipeline_modules
from app.modules.sports_odds.api import router as sports_odds_router
from app.modules.sports_odds import models as sports_odds_models
from app.normalization import models as normalization_models
from app.pipeline import models as pipeline_models  # ensure tables are registered
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
_ = pipeline_models


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
    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(CorrelationMiddleware)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── /health  — full dependency check ──────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["observability"])
    def health() -> HealthResponse:
        from cache.client import get_redis

        deps: dict[str, DependencyStatus] = {}

        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            deps["postgres"] = DependencyStatus(status="ok")
        except Exception as exc:
            deps["postgres"] = DependencyStatus(status="error", detail=str(exc))

        if settings.cache_enabled:
            try:
                client = get_redis()
                if client is None:
                    raise RuntimeError("Redis client unavailable")
                client.ping()
                deps["redis"] = DependencyStatus(status="ok")
            except Exception as exc:
                deps["redis"] = DependencyStatus(status="error", detail=str(exc))

        overall = "ok" if all(d.status == "ok" for d in deps.values()) else "degraded"
        return HealthResponse(
            status=overall,
            app=settings.app_name,
            environment=settings.app_env,
            dependencies=deps,
        )

    # ── /live  — liveness probe (process alive, no deep checks) ───────────────
    @app.get("/live", tags=["observability"], include_in_schema=False)
    def liveness() -> JSONResponse:
        """Kubernetes / Coolify liveness probe.

        Returns 200 as long as the process is running and the event loop is
        responsive.  Does NOT check database or Redis — use /ready for that.
        """
        return JSONResponse({"status": "alive", "app": settings.app_name})

    # ── /ready  — readiness probe (can the app serve traffic?) ───────────────
    @app.get("/ready", tags=["observability"], include_in_schema=False)
    def readiness() -> JSONResponse:
        """Kubernetes / Coolify readiness probe.

        Verifies that all required dependencies are reachable.
        Returns 200 if ready, 503 if any critical dependency is down.

        Checks
        ──────
        • PostgreSQL: SELECT 1
        • Redis: PING (only when cache_enabled=true)
        • Scheduler: running flag (only when scheduler_enabled=true)
        """
        checks: dict[str, str] = {}
        ready = True

        # PostgreSQL
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"
            ready = False

        # Redis
        if settings.cache_enabled:
            try:
                from cache.client import get_redis
                client = get_redis()
                if client is None:
                    raise RuntimeError("client unavailable")
                client.ping()
                checks["redis"] = "ok"
            except Exception as exc:
                checks["redis"] = f"error: {exc}"
                ready = False

        # Scheduler
        if settings.scheduler_enabled:
            scheduler = getattr(app.state, "scheduler", None)
            if scheduler is not None and scheduler.running:
                checks["scheduler"] = "ok"
            else:
                checks["scheduler"] = "not running"
                ready = False

        status_code = 200 if ready else 503
        return JSONResponse(
            {"ready": ready, "checks": checks, "app": settings.app_name},
            status_code=status_code,
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    auth_dep = [Depends(verify_api_key)]
    app.include_router(api_router, dependencies=auth_dep)
    app.include_router(poupi_baby_router, dependencies=auth_dep)
    app.include_router(pipeline_router, dependencies=auth_dep)
    app.include_router(documentation_router, dependencies=auth_dep)
    app.include_router(data_quality_router, dependencies=auth_dep)
    app.include_router(crypto_router, dependencies=auth_dep)
    app.include_router(real_estate_router, dependencies=auth_dep)
    app.include_router(sports_odds_router, dependencies=auth_dep)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app
