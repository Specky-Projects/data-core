"""Tests for ObservationContract — Phase 2.2."""

from app.observation.adapter import (
    from_funding_rate,
    from_open_interest,
    from_raw_dict,
    from_signal_event,
)
from app.observation.contract import (
    OBSERVATION_VERSION,
    ObservationContract,
    ObservationQuality,
    ObservationSnapshot,
    ObservationType,
    stable_hash,
)
from app.observation.repository import InMemoryObservationRepository
from app.observation.timeline import ObservationTimeline


# ── Contract ───────────────────────────────────────────────────────────────────


def test_create_computes_payload_hash_automatically() -> None:
    payload = {"price": 50000.0, "symbol": "BTCUSDT"}
    obs = ObservationContract.create(
        observation_id="obs-1",
        producer="sip/strategy-a",
        observed_at="2026-06-30T12:00:00+00:00",
        observation_type=ObservationType.PRICE,
        payload=payload,
    )
    assert obs.payload_hash == stable_hash(payload)
    assert obs.verify_payload_integrity()


def test_schema_version_is_canonical() -> None:
    obs = ObservationContract.create(
        observation_id="obs-2",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.GENERIC,
        payload={"x": 1},
    )
    assert obs.schema_version == OBSERVATION_VERSION


def test_validate_rejects_empty_payload() -> None:
    obs = ObservationContract(
        observation_id="obs-3",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.SIGNAL,
        payload={},
        payload_hash="irrelevant",
    )
    errors = obs.validate()
    assert any("payload" in e for e in errors)


def test_validate_detects_payload_tampering() -> None:
    obs = ObservationContract.create(
        observation_id="obs-4",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.VOLUME,
        payload={"v": 1000},
    )
    # Simulate tampering by constructing a copy with modified payload but original hash
    tampered = ObservationContract(
        observation_id=obs.observation_id,
        producer=obs.producer,
        observed_at=obs.observed_at,
        observation_type=obs.observation_type,
        payload={"v": 9999},
        payload_hash=obs.payload_hash,
    )
    assert not tampered.verify_payload_integrity()
    errors = tampered.validate()
    assert any("integrity" in e for e in errors)


def test_observation_is_immutable() -> None:
    obs = ObservationContract.create(
        observation_id="obs-frozen",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.SIGNAL,
        payload={"x": 1},
    )
    try:
        obs.observation_id = "mutated"  # type: ignore[misc]
        assert False, "should have raised"
    except (AttributeError, TypeError):
        pass


# ── Snapshot ───────────────────────────────────────────────────────────────────


def test_snapshot_captures_observation_state() -> None:
    obs = ObservationContract.create(
        observation_id="obs-snap",
        producer="whalefi/binance",
        observed_at="2026-06-30T00:00:00",
        observation_type=ObservationType.FUNDING,
        payload={"rate": 0.001},
    )
    snap = ObservationSnapshot.from_observation(obs, "2026-06-30T00:00:01")
    assert snap.observation_id == obs.observation_id
    assert snap.verify(obs)


def test_snapshot_detects_tampered_observation() -> None:
    obs = ObservationContract.create(
        observation_id="obs-snap2",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.GENERIC,
        payload={"k": "v"},
    )
    snap = ObservationSnapshot.from_observation(obs, "2026-01-01T00:00:01")

    different_obs = ObservationContract.create(
        observation_id="obs-snap2",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.GENERIC,
        payload={"k": "CHANGED"},
    )
    assert not snap.verify(different_obs)


# ── Timeline ───────────────────────────────────────────────────────────────────


def test_timeline_preserves_insertion_order() -> None:
    tl = ObservationTimeline(lineage_id="lin-tl")
    for i in range(3):
        tl.append(ObservationContract.create(
            observation_id=f"obs-{i}",
            producer="p",
            observed_at=f"2026-06-30T00:0{i}:00",
            observation_type=ObservationType.SIGNAL,
            payload={"i": i},
        ))
    assert tl.count() == 3
    assert tl.first().observation_id == "obs-0"
    assert tl.latest().observation_id == "obs-2"


def test_timeline_replay_window_filters_correctly() -> None:
    tl = ObservationTimeline(lineage_id="lin-window")
    for hour in [10, 11, 12, 13, 14]:
        tl.append(ObservationContract.create(
            observation_id=f"obs-h{hour}",
            producer="p",
            observed_at=f"2026-06-30T{hour:02d}:00:00",
            observation_type=ObservationType.PRICE,
            payload={"h": hour},
        ))
    window = tl.replay_window("2026-06-30T11:00:00", "2026-06-30T13:00:00")
    assert len(window) == 3
    assert all(o.observation_id in {"obs-h11", "obs-h12", "obs-h13"} for o in window)


def test_timeline_hash_changes_when_observation_added() -> None:
    tl = ObservationTimeline(lineage_id="lin-hash")
    h0 = tl.timeline_hash
    tl.append(ObservationContract.create(
        observation_id="obs-new",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.GENERIC,
        payload={"x": 1},
    ))
    assert tl.timeline_hash != h0


# ── Repository ─────────────────────────────────────────────────────────────────


def test_repository_save_and_get() -> None:
    repo = InMemoryObservationRepository()
    obs = ObservationContract.create(
        observation_id="obs-repo",
        producer="p",
        observed_at="2026-01-01T00:00:00",
        observation_type=ObservationType.VOLUME,
        payload={"v": 500},
    )
    repo.save(obs)
    assert repo.get("obs-repo") == obs


def test_repository_find_by_type() -> None:
    repo = InMemoryObservationRepository()
    for i, otype in enumerate([ObservationType.FUNDING, ObservationType.SIGNAL, ObservationType.FUNDING]):
        repo.save(ObservationContract.create(
            observation_id=f"obs-{i}",
            producer="p",
            observed_at="2026-01-01T00:00:00",
            observation_type=otype,
            payload={"i": i},
        ))
    funding = repo.find_by_type(ObservationType.FUNDING)
    assert len(funding) == 2


# ── Adapters ───────────────────────────────────────────────────────────────────


def test_from_signal_event() -> None:
    event = {
        "signal_id": "sig-001",
        "strategy": "spec",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "confidence": 0.8,
        "timestamp": "2026-06-30T10:00:00",
    }
    obs = from_signal_event(event)
    assert obs.observation_type == ObservationType.SIGNAL
    assert obs.symbol == "BTCUSDT"
    assert obs.verify_payload_integrity()


def test_from_funding_rate() -> None:
    obs = from_funding_rate("BTCUSDT", 0.001, "2026-06-30T08:00:00", "binance")
    assert obs.observation_type == ObservationType.FUNDING
    assert obs.symbol == "BTCUSDT"
    assert obs.quality == ObservationQuality.VERIFIED
    assert obs.verify_payload_integrity()


def test_from_open_interest() -> None:
    obs = from_open_interest("ETHUSDT", 1_200_000.0, "2026-06-30T08:00:00", "bybit")
    assert obs.observation_type == ObservationType.OPEN_INTEREST
    assert obs.symbol == "ETHUSDT"
    assert obs.verify_payload_integrity()


def test_from_raw_dict() -> None:
    obs = from_raw_dict(
        observation_id="raw-1",
        producer="collector/custom",
        observed_at="2026-06-30T09:00:00",
        observation_type=ObservationType.MACRO,
        payload={"cpi": 3.2},
    )
    assert obs.observation_type == ObservationType.MACRO
    assert obs.verify_payload_integrity()
