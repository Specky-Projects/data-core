"""
basketball/nba — thin re-export shim.

All production code lives in app.modules.nba.quant.*.
This package allows new code to use the basketball.* namespace
while legacy imports (app.modules.nba.quant.*) keep working unchanged.
"""
from app.modules.nba.quant import api, analytics, collector  # noqa: F401
from app.modules.nba.quant import features, metrics, models  # noqa: F401
from app.modules.nba.quant import odds_collector, out_of_sample  # noqa: F401
from app.modules.nba.quant import paper_betting, pipeline, signals  # noqa: F401
from app.modules.nba.quant import telegram_alerts  # noqa: F401
