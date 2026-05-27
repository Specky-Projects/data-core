"""ReplayabilityAnalyzer — deterministic replay, sequence gaps, snapshot consistency."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.operational_truth.dto import ReplayabilityTruth, classify_score

RUNTIME_DATA_DIR = Path(os.getenv("RUNTIME_DATA_DIR", "runtime-data"))

_REPLAY_JSONL_PATTERNS = [
    "scheduler_execution_drift.jsonl",
    "scheduler_lifecycle.jsonl",
    "stability_log.jsonl",
    "governance_history.jsonl",
]

_HEARTBEAT_FILES = [
    "scheduler_heartbeat.json",
    "worker_heartbeat.json",
    "scheduler_watchdog_snapshot.json",
]


def _count_replay_files() -> int:
    found = 0
    for name in _REPLAY_JSONL_PATTERNS + _HEARTBEAT_FILES:
        if (RUNTIME_DATA_DIR / name).exists():
            found += 1
    return found


def _latest_snapshot_age() -> float | None:
    """Return age in seconds of the most recently modified replay file."""
    ages: list[float] = []
    for name in _HEARTBEAT_FILES:
        p = RUNTIME_DATA_DIR / name
        try:
            if p.exists():
                ages.append(time.time() - p.stat().st_mtime)
        except Exception:
            pass
    return min(ages) if ages else None


def _detect_sequence_gaps() -> tuple[bool, int]:
    """Scan backlog history JSONL for sequence gaps; return (gap_detected, estimated_missing)."""
    backlog_path = RUNTIME_DATA_DIR / "scheduler_backlog_history.jsonl"
    if not backlog_path.exists():
        return False, 0
    try:
        lines = backlog_path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            return False, 0
        timestamps: list[float] = []
        for line in lines[-50:]:  # only inspect recent 50 records
            try:
                record = json.loads(line)
                ts = record.get("timestamp") or record.get("written_at")
                if ts:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    timestamps.append(dt.timestamp())
            except Exception:
                continue
        if len(timestamps) < 2:
            return False, 0
        timestamps.sort()
        gaps = 0
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i - 1]
            if interval > 3600:  # >1h gap between consecutive records
                gaps += 1
        return gaps > 0, gaps
    except Exception:
        return False, 0


def _check_snapshot_consistency() -> bool:
    """Basic check: scheduler_heartbeat.json and worker_heartbeat.json both readable."""
    for name in ["scheduler_heartbeat.json", "worker_heartbeat.json"]:
        p = RUNTIME_DATA_DIR / name
        if p.exists():
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return False
    return True


def analyze_replayability() -> ReplayabilityTruth:
    findings: list[str] = []
    now = datetime.now(timezone.utc)

    replay_files = _count_replay_files()
    snapshot_age = _latest_snapshot_age()
    gap_detected, missing_estimated = _detect_sequence_gaps()
    snapshot_ok = _check_snapshot_consistency()

    if replay_files == 0:
        findings.append("replay_files_missing: no runtime-data files found")
    elif replay_files < 3:
        findings.append(f"replay_files_partial: only {replay_files} replay files present")

    if snapshot_age is None:
        findings.append("replay_snapshot_age_unknown: no heartbeat files found")
    elif snapshot_age > 3600:
        findings.append(f"replay_snapshot_stale: {snapshot_age:.0f}s since last snapshot")

    if gap_detected:
        findings.append(f"replay_sequence_gaps: ~{missing_estimated} gap(s) detected in backlog history")

    if not snapshot_ok:
        findings.append("replay_snapshot_corrupt: heartbeat file unreadable or malformed")

    # Scores
    replay_score = 100
    if replay_files == 0:
        replay_score -= 50
    elif replay_files < 3:
        replay_score -= 20

    if snapshot_age is not None and snapshot_age > 7200:
        replay_score -= 30
    elif snapshot_age is not None and snapshot_age > 3600:
        replay_score -= 15

    if gap_detected:
        replay_score -= 25

    if not snapshot_ok:
        replay_score -= 20

    replay_score = max(0, replay_score)

    # Determinism score: based on snapshot consistency + no gaps
    determinism = 100
    if gap_detected:
        determinism -= 40
    if not snapshot_ok:
        determinism -= 30
    if replay_files < 3:
        determinism -= 15
    determinism = max(0, determinism)

    # Reconstruction confidence
    reconstruction = 100
    if replay_files == 0:
        reconstruction = 10
    elif snapshot_age is not None and snapshot_age > 3600:
        reconstruction -= 20
    if gap_detected:
        reconstruction -= 30
    reconstruction = max(0, reconstruction)

    return ReplayabilityTruth(
        score=replay_score,
        determinism_score=determinism,
        reconstruction_confidence=reconstruction,
        status=classify_score(replay_score),
        sequence_gaps_detected=gap_detected,
        missing_events_estimated=missing_estimated,
        snapshot_consistency=snapshot_ok,
        replay_files_found=replay_files,
        replay_age_seconds=snapshot_age,
        findings=findings,
        evaluated_at=now,
    )
