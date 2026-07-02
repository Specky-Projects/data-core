from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.analytics import models as analytics_models
from app.data_quality import models as data_quality_models
from app.data_quality.crypto import models as crypto_data_quality_models
from app.documentation import models as documentation_models
from app.incident_bus import models as incident_bus_models
from app.incident_history import models as incident_history_models
from app.modules.basketball.wnba import models as wnba_models
from app.modules.crypto.edge import alert_state_model as crypto_edge_alert_state_models
from app.modules.crypto.edge import forward_model as crypto_edge_forward_models
from app.modules.crypto.edge import models as crypto_edge_models
from app.modules.nba import models as nba_models
from app.modules.nba.quant import models as nba_quant_models
from app.modules.sports_odds import models as sports_odds_models
from app.modules.trading.validation import models as trading_validation_models
from app.normalization import models as normalization_models
from app.observability import models as observability_models
from app.observer_framework import models as observer_framework_models
from app.pipeline import models as pipeline_models
from app.raw import models as raw_models
from app.scrapers import models as scrapers_models
from app.universal_execution_log import db_models as universal_execution_log_models
from app.watchdog import models as watchdog_models
from core.config import settings
from database.models import Base

_ = nba_models
_ = nba_quant_models
_ = sports_odds_models
_ = raw_models
_ = normalization_models
_ = analytics_models
_ = data_quality_models
_ = documentation_models
_ = crypto_data_quality_models
_ = incident_bus_models
_ = incident_history_models
_ = wnba_models
_ = crypto_edge_alert_state_models
_ = crypto_edge_forward_models
_ = crypto_edge_models
_ = trading_validation_models
_ = observability_models
_ = observer_framework_models
_ = pipeline_models
_ = scrapers_models
_ = universal_execution_log_models
_ = watchdog_models

# telegram_delivery_audit is intentionally raw-SQL-only (see
# app/observation_engine/adapters/telegram.py) — no ORM model exists for it,
# so autogenerate must be told not to treat it as a drift/removal candidate.
_RAW_SQL_ONLY_TABLES = {"telegram_delivery_audit"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in _RAW_SQL_ONLY_TABLES:
        return False
    if type_ == "index" and getattr(object, "table", None) is not None:
        if object.table.name in _RAW_SQL_ONLY_TABLES:
            return False
    return True


config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
