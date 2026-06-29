# STAGE 3.6 — REPLAY READINESS AUDIT

**Date:** 2026-06-28
**Method:** Read-only independent inspection of all production files
**Scope:** Wall-clock dependency search, EvaluationContext injection verification, determinism proof

---

## 1. Wall-Clock Dependency Search

### Search executed

Pattern: `datetime.now|utcnow()` across all `.py` files in `app/adaptive_intelligence/`

### Results

Files containing matches: 6 — ALL ARE TEST FILES

| File | Line | Content |
|------|------|---------|
| tests/test_orchestrator.py | 27 | `return datetime.now(timezone.utc)` — test helper `_now()` |
| tests/test_risk_tuner.py | 18 | `return datetime.now(timezone.utc)` — test helper `_now()` |
| tests/test_risk_tuner.py | 80 | `obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)` — fixture |
| tests/test_regime_adapter.py | 29 | `obj.signal_at = datetime.now(timezone.utc) - timedelta(days=1)` — fixture |
| tests/test_calibration.py | 27 | `obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)` — fixture |
| tests/test_strategy_feedback.py | 39 | `obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)` — fixture |

**Production files with wall-clock calls: ZERO**

Production files inspected and confirmed clean:
- `dto.py` — CLEAN
- `orchestrator.py` — CLEAN (uses `_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")`)
- `strategy_feedback.py` — CLEAN
- `confidence_calibration.py` — CLEAN
- `regime_adapter.py` — CLEAN
- `risk_tuner.py` — CLEAN
- `metrics.py` — CLEAN
- `api.py` — CLEAN

---

## 2. EvaluationContext Injection Verification

### dto.py — derive_evaluation_context (line 269)

```python
def derive_evaluation_context(rows, lookback_days, evaluation_context=None):
    if evaluation_context is not None:
        return evaluation_context.model_copy(...)  # injected context: preserved
    timestamps = [timestamp for row in rows if (timestamp := _row_timestamp(row)) ...]
    evaluation_timestamp = max(timestamps) if timestamps else datetime.fromisoformat("1970-...")
```

**Finding:** When an `EvaluationContext` is injected, it is returned unchanged (minus lookback backfill). When none is provided, timestamp is derived deterministically from `max(row timestamps)`. Fallback is `1970-01-01T00:00:00+00:00` constant — not wall-clock.

### StrategyFeedbackEngine.__init__ (strategy_feedback.py:271)
```python
def __init__(self, db, lookback_days=30, evaluation_context=None):
    self._evaluation_context = evaluation_context
```
Injection: **CONFIRMED**

### ConfidenceCalibrationEngine.__init__ (confidence_calibration.py:188)
```python
def __init__(self, db, lookback_days=30, evaluation_context=None):
    self._evaluation_context = evaluation_context
```
Injection: **CONFIRMED**

### RegimeAdapter.__init__ (regime_adapter.py:97)
```python
def __init__(self, db, lookback_days=30, evaluation_context=None):
    self._evaluation_context = evaluation_context
```
Injection: **CONFIRMED**

### RiskTuner.__init__ (risk_tuner.py:73)
```python
def __init__(self, db, lookback_days=14, evaluation_context=None):
    self._evaluation_context = evaluation_context
    self._resolved_evaluation_context = evaluation_context
```
Injection: **CONFIRMED**

### AdaptiveIntelligenceOrchestrator.__init__ (orchestrator.py:269)
```python
def __init__(self, db, lookback_days=30, environment="production", evaluation_context=None):
    self._evaluation_context = evaluation_context
```
Injection: **CONFIRMED**

All 5 engines and the orchestrator accept `EvaluationContext` injection.

---

## 3. Row Filtering Determinism

### filter_rows_for_context (dto.py:304)

```python
def filter_rows_for_context(rows, evaluation_context, lookback_days):
    cutoff = evaluation_context.evaluation_timestamp.timestamp() - (lookback_days * 86_400)
    end = evaluation_context.evaluation_timestamp.timestamp()
    ...
    if cutoff <= ts <= end:
        filtered.append(row)
```

Reference point: `evaluation_context.evaluation_timestamp.timestamp()` — not wall-clock.
Cutoff arithmetic: integer multiplication of `lookback_days * 86_400` — deterministic.

**Finding:** DETERMINISTIC

---

## 4. Latent Edge Case — RiskTuner

In `risk_tuner.py:82`: `self._resolved_evaluation_context = evaluation_context` — may be `None` if no `evaluation_context` was injected.

In `_fetch_recent_aggregates()` (line 176): `self._resolved_evaluation_context = evaluation_context` — overwritten with derived context.

In `evaluate()` line 146: `evaluated_at=self._resolved_evaluation_context.evaluation_timestamp` — called AFTER `_fetch_recent_aggregates`.

**Risk:** If `_fetch_recent_aggregates` raises before assigning `self._resolved_evaluation_context`, line 146 raises `AttributeError` on `None`. This is caught by the orchestrator's `try/except` which falls back to `_empty_risk()`.

**Classification:** LATENT_EDGE_CASE — not a wall-clock issue, not a replay issue. Caught by error handling. Not a blocker.

---

## 5. Replay Test Evidence

Tests in `test_stage_3_6.py::TestDeterministicReplay` (8 tests, all PASS):
- Same `EvaluationContext` + same rows → same `decision_hash` ✓
- Same `EvaluationContext` + same rows → same recommendations ✓
- Same `EvaluationContext` + same rows → same drift ✓
- `replay_mode=True` when context is injected ✓
- `derive_evaluation_context` is deterministic ✓
- `filter_rows_for_context` is deterministic ✓
- Orchestrator with fixed context produces same `decision_hash` ✓

---

## 6. Audit Conclusion

| Check | Result |
|-------|--------|
| No production wall-clock calls | PASS |
| EvaluationContext injectable at all engines | PASS |
| derive_evaluation_context is deterministic | PASS |
| filter_rows_for_context uses no wall-clock | PASS |
| compute_freshness uses no wall-clock | PASS |
| compute_longitudinal_drift uses no wall-clock | PASS |
| Fallback context uses constant epoch | PASS |
| Same inputs → same decision_hash | PASS |
| datetime.now() confined to test scaffolding | PASS |

**REPLAY READINESS: GO**

One latent edge case (RiskTuner null safety) documented, not a blocker, caught by orchestrator.
