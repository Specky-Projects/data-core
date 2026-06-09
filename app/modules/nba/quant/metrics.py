from prometheus_client import Counter, Gauge

nba_q_games_collected_total = Counter(
    "nba_q_games_collected_total",
    "Total NBA games collected",
    ["season"],
)

nba_q_signals_total = Counter(
    "nba_q_signals_total",
    "Total NBA quant signals generated",
    ["setup"],
)

nba_q_bets_settled_total = Counter(
    "nba_q_bets_settled_total",
    "Total NBA quant bets settled",
    ["setup", "result"],
)

nba_q_setup_roi = Gauge(
    "nba_q_setup_roi",
    "ROI per setup (%)",
    ["setup"],
)

nba_q_setup_win_rate = Gauge(
    "nba_q_setup_win_rate",
    "Win rate per setup (%)",
    ["setup"],
)

nba_q_setup_classification = Gauge(
    "nba_q_setup_classification",
    "Edge classification (1=PROFITABLE, 0=NEUTRAL, -1=LOSING)",
    ["setup"],
)

nba_q_global_roi = Gauge("nba_q_global_roi", "Global quant ROI (%)")
nba_q_global_pnl = Gauge("nba_q_global_pnl", "Global quant PnL (units)")
nba_q_total_games = Gauge("nba_q_total_games", "Total NBA games in DB")
nba_q_total_signals = Gauge("nba_q_total_signals", "Total quant signals")

nba_q_pipeline_runs_total = Counter(
    "nba_q_pipeline_runs_total",
    "Total NBA quant pipeline runs",
    ["status"],
)

nba_q_pipeline_duration_seconds = Gauge(
    "nba_q_pipeline_duration_seconds",
    "Last NBA quant pipeline run duration (seconds)",
)

nba_q_features_computed_total = Counter(
    "nba_q_features_computed_total",
    "Total NBA game features computed",
)

nba_q_bets_pending = Gauge("nba_q_bets_pending", "Current pending NBA quant bets")

# ── Phase 3 ───────────────────────────────────────────────────────────────────

nba_q_odds_upserted_total = Counter(
    "nba_q_odds_upserted_total",
    "Total NBA odds records upserted from The Odds API",
)

nba_q_odds_games_matched = Gauge(
    "nba_q_odds_games_matched",
    "Games matched on last odds fetch",
)

nba_q_alerts_sent_total = Counter(
    "nba_q_alerts_sent_total",
    "Total Telegram alerts sent",
    ["setup"],
)

nba_q_oos_roi = Gauge(
    "nba_q_oos_roi",
    "Out-of-sample ROI per setup (%)",
    ["setup", "window"],  # window: train | test
)

nba_q_oos_verdict = Gauge(
    "nba_q_oos_verdict",
    "OOS verdict (2=CONFIRMED, 1=MARGINAL, 0=DEGRADED, -1=NO_EDGE)",
    ["setup"],
)

nba_q_setup_sharpe = Gauge(
    "nba_q_setup_sharpe",
    "Per-bet Sharpe ratio per setup",
    ["setup", "window"],
)

nba_q_setup_profit_factor = Gauge(
    "nba_q_setup_profit_factor",
    "Profit factor per setup (gross_profit / gross_loss)",
    ["setup", "window"],
)

nba_q_setup_max_drawdown = Gauge(
    "nba_q_setup_max_drawdown",
    "Max drawdown per setup (units)",
    ["setup", "window"],
)
