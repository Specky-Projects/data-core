from prometheus_client import Counter, Gauge

wnba_q_games_collected_total = Counter(
    "wnba_q_games_collected_total",
    "Total WNBA games collected",
    ["season"],
)

wnba_q_signals_total = Counter(
    "wnba_q_signals_total",
    "Total WNBA quant signals generated",
    ["setup"],
)

wnba_q_bets_settled_total = Counter(
    "wnba_q_bets_settled_total",
    "Total WNBA quant bets settled",
    ["setup", "result"],
)

wnba_q_setup_roi = Gauge(
    "wnba_q_setup_roi",
    "WNBA ROI per setup (%)",
    ["setup"],
)

wnba_q_setup_win_rate = Gauge(
    "wnba_q_setup_win_rate",
    "WNBA win rate per setup (%)",
    ["setup"],
)

wnba_q_setup_classification = Gauge(
    "wnba_q_setup_classification",
    "WNBA edge classification (1=PROFITABLE, 0=NEUTRAL, -1=LOSING)",
    ["setup"],
)

wnba_q_global_roi = Gauge("wnba_q_global_roi", "WNBA global quant ROI (%)")
wnba_q_global_pnl = Gauge("wnba_q_global_pnl", "WNBA global quant PnL (units)")
wnba_q_total_games = Gauge("wnba_q_total_games", "Total WNBA games in DB")
wnba_q_total_signals = Gauge("wnba_q_total_signals", "Total WNBA quant signals")

wnba_q_pipeline_runs_total = Counter(
    "wnba_q_pipeline_runs_total",
    "Total WNBA quant pipeline runs",
    ["status"],
)

wnba_q_pipeline_duration_seconds = Gauge(
    "wnba_q_pipeline_duration_seconds",
    "Last WNBA quant pipeline run duration (seconds)",
)

wnba_q_features_computed_total = Counter(
    "wnba_q_features_computed_total",
    "Total WNBA game features computed",
)

wnba_q_bets_pending = Gauge("wnba_q_bets_pending", "Current pending WNBA quant bets")

wnba_q_odds_upserted_total = Counter(
    "wnba_q_odds_upserted_total",
    "Total WNBA odds records upserted from The Odds API",
)

wnba_q_alerts_sent_total = Counter(
    "wnba_q_alerts_sent_total",
    "Total WNBA Telegram alerts sent",
    ["setup"],
)
