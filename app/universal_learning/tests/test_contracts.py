from app.universal_learning.contracts import (
    LearningEvidence,
    LearningKnowledge,
    LearningMaturity,
    LearningSignal,
    LearningSignalKind,
    LearningSnapshot,
    LearningSource,
    LearningStatistics,
    LearningTimeline,
    LearningTimelineEntry,
    UniversalLearningPipeline,
    UniversalLearningRepository,
)


def _snapshot() -> LearningSnapshot:
    return LearningSnapshot(
        snapshot_id="snap-001",
        domain="crypto",
        strategy="specky",
        captured_at="2026-06-30T00:00:00Z",
        maturity=LearningMaturity.STABLE,
        sample_size=100,
        evidence_refs=("ev-001",),
    )


def test_evidence_validates_required_fields() -> None:
    ev = LearningEvidence(
        evidence_id="ev-001",
        source=LearningSource.MIRROR,
        source_ref="mirror:trade:001",
        captured_at="2026-06-30T00:00:00Z",
        payload_hash="abc",
    )
    assert ev.validate() == []


def test_evidence_invalid_quality_score() -> None:
    ev = LearningEvidence(
        evidence_id="ev-001",
        source=LearningSource.OUTCOME,
        source_ref="outcome:001",
        captured_at="2026-06-30T00:00:00Z",
        payload_hash="abc",
        quality_score=1.5,
    )
    errors = ev.validate()
    assert any("quality_score" in e for e in errors)


def test_snapshot_validates() -> None:
    snap = _snapshot()
    assert snap.validate() == []


def test_snapshot_invalid_sample_size() -> None:
    snap = LearningSnapshot(
        snapshot_id="s1",
        domain="crypto",
        strategy=None,
        captured_at="t",
        maturity=LearningMaturity.BOOTSTRAP,
        sample_size=-1,
        evidence_refs=(),
    )
    errors = snap.validate()
    assert any("sample_size" in e for e in errors)


def test_signal_advisory_only() -> None:
    signal = LearningSignal(
        signal_id="sig-001",
        kind=LearningSignalKind.EDGE_CONFIRMATION,
        domain="crypto",
        strategy="specky",
        detected_at="2026-06-30T00:00:00Z",
        snapshot_ref="snap-001",
        magnitude=0.7,
        direction="POSITIVE",
        description="Edge confirmed over 100 samples",
    )
    assert signal.ADVISORY_ONLY is True
    assert signal.validate() == []


def test_signal_invalid_magnitude() -> None:
    signal = LearningSignal(
        signal_id="sig-002",
        kind=LearningSignalKind.REGIME_SHIFT,
        domain="crypto",
        strategy=None,
        detected_at="t",
        snapshot_ref="snap-001",
        magnitude=2.0,
        direction="NEGATIVE",
        description="regime shift",
    )
    assert any("magnitude" in e for e in signal.validate())


def test_timeline_latest_entry() -> None:
    entry = LearningTimelineEntry(
        entry_id="e1",
        snapshot_ref="snap-001",
        recorded_at="2026-06-30T00:00:00Z",
        maturity=LearningMaturity.STABLE,
    )
    timeline = LearningTimeline(
        timeline_id="tl-001",
        domain="crypto",
        strategy="specky",
        entries=(entry,),
        from_date="2026-01-01",
        to_date="2026-06-30",
    )
    assert timeline.latest_entry() == entry
    assert timeline.validate() == []


def test_timeline_empty_entries_invalid() -> None:
    timeline = LearningTimeline(
        timeline_id="tl-001",
        domain="crypto",
        strategy=None,
        entries=(),
        from_date="2026-01-01",
        to_date="2026-06-30",
    )
    errors = timeline.validate()
    assert any("entry" in e for e in errors)


def test_statistics_validates() -> None:
    stats = LearningStatistics(
        stats_id="stats-001",
        domain="crypto",
        strategy="specky",
        computed_at="2026-06-30T00:00:00Z",
        sample_size=100,
        win_rate=0.55,
        avg_confidence=0.72,
    )
    assert stats.validate() == []


def test_statistics_invalid_rate() -> None:
    stats = LearningStatistics(
        stats_id="stats-001",
        domain="crypto",
        strategy=None,
        computed_at="t",
        sample_size=10,
        win_rate=1.5,
    )
    errors = stats.validate()
    assert any("win_rate" in e for e in errors)


def test_knowledge_validates() -> None:
    k = LearningKnowledge(
        knowledge_id="k-001",
        domain="crypto",
        claim="B2B_FADE edge confirmed at N=100",
        confidence=0.8,
        derived_from=("snap-001",),
        validated=True,
    )
    assert k.validate() == []


def test_knowledge_cannot_be_both_valid_and_invalid() -> None:
    k = LearningKnowledge(
        knowledge_id="k-001",
        domain="crypto",
        claim="contradictory state",
        confidence=0.5,
        derived_from=("snap-001",),
        validated=True,
        invalidated=True,
    )
    errors = k.validate()
    assert any("validated and invalidated" in e for e in errors)


def test_repository_is_abstract() -> None:
    repo = UniversalLearningRepository()
    try:
        repo.save_snapshot(_snapshot())
        assert False
    except NotImplementedError:
        pass


def test_pipeline_is_advisory_only() -> None:
    pipeline = UniversalLearningPipeline()
    assert pipeline.ADVISORY_ONLY is True
