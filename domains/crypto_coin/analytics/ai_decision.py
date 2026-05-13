"""Autonomous decision layer fed by storage analytics."""

from __future__ import annotations


def build_ai_decision(
    *,
    replay: dict,
    confidence_performance: list[dict],
    regimes: list[dict],
    shadow: dict,
    strategy_regimes: list[dict],
) -> dict:
    """Produce staged machine decisions without requiring human review."""
    actions = []

    replay_ready = bool(replay.get("ready"))
    if replay_ready:
        if (replay.get("net_pnl_pct") or 0) < 0:
            actions.append({
                "type": "strategy_regression",
                "stage": "shadow_test",
                "confidence": 82,
                "decision": "freeze_live_promotion",
                "reason": "Replay atual ficou negativo; manter mudancas fora do live ate shadow/paper melhorar.",
            })
        if (replay.get("acceptance_change_rate") or 0) > 25:
            actions.append({
                "type": "signal_drift",
                "stage": "paper_test",
                "confidence": 74,
                "decision": "extend_validation_window",
                "reason": "A estrategia atual alterou muitas decisoes antigas; ampliar validacao automatica.",
            })

    weak_conf = [
        row for row in confidence_performance
        if (row.get("total_trades") or 0) >= 3 and (row.get("net_pnl") or 0) < 0
    ]
    strong_conf = [
        row for row in confidence_performance
        if (row.get("total_trades") or 0) >= 3 and (row.get("net_pnl") or 0) > 0
    ]
    if weak_conf and strong_conf:
        threshold = min(row.get("confidence_bucket") or 0 for row in strong_conf)
        actions.append({
            "type": "confidence_gate",
            "stage": "shadow_test",
            "confidence": 78,
            "decision": "test_min_confidence",
            "value": threshold,
            "reason": f"Buckets abaixo de {threshold}% estao piores que buckets superiores.",
        })

    weak_regimes = [
        row for row in regimes
        if (row.get("total_trades") or 0) >= 6 and (row.get("net_pnl") or 0) < 0
    ]
    for row in weak_regimes[:3]:
        actions.append({
            "type": "regime_gate",
            "stage": "paper_test",
            "confidence": 76,
            "decision": "penalize_or_block_regime",
            "value": row.get("regime"),
            "reason": f"Regime {row.get('regime')} tem P&L negativo e amostra suficiente.",
        })

    blocked = ((replay or {}).get("blocked_outcomes") or {}).get("by_reason") or []
    harmful_blocks = [
        row for row in blocked
        if (row.get("count") or 0) >= 3 and (row.get("avg_pnl_pct") or 0) < 0
    ]
    profitable_blocks = [
        row for row in blocked
        if (row.get("count") or 0) >= 3 and (row.get("avg_pnl_pct") or 0) > 0
    ]
    for row in harmful_blocks[:2]:
        actions.append({
            "type": "blocked_signal_validation",
            "stage": "candidate_live",
            "confidence": 80,
            "decision": "keep_block",
            "value": row.get("reason"),
            "reason": "Sinais bloqueados por este motivo teriam perdido no replay futuro.",
        })
    for row in profitable_blocks[:2]:
        actions.append({
            "type": "blocked_signal_validation",
            "stage": "shadow_test",
            "confidence": 72,
            "decision": "relax_filter_experiment",
            "value": row.get("reason"),
            "reason": "Sinais bloqueados por este motivo teriam dado retorno positivo no replay futuro.",
        })

    if (shadow.get("closed") or 0) >= 10 and (shadow.get("net_pnl_pct") or 0) > 0:
        actions.append({
            "type": "shadow_promotion",
            "stage": "paper_test",
            "confidence": 70,
            "decision": "promote_shadow_rule_to_paper",
            "reason": "Shadow live fechou amostra positiva suficiente para teste em paper.",
        })

    best_by_regime = _best_versions_by_regime(strategy_regimes)
    if best_by_regime:
        actions.append({
            "type": "strategy_version_regime_routing",
            "stage": "observe",
            "confidence": 68,
            "decision": "prefer_best_version_by_regime",
            "value": best_by_regime,
            "reason": "Ha versoes com desempenho distinto por regime; usar como entrada do roteamento IA.",
        })

    return {
        "mode": "ai_autonomous",
        "human_review_required": False,
        "live_auto_apply": False,
        "live_apply_rule": "somente apos evidencia positiva em shadow e paper",
        "actions": actions,
    }


def _best_versions_by_regime(rows: list[dict]) -> dict:
    best = {}
    for row in rows:
        regime = row.get("regime") or "unknown"
        current = best.get(regime)
        if current is None or (row.get("net_pnl") or 0) > (current.get("net_pnl") or 0):
            best[regime] = row
    return best
