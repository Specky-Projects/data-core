"""Regression test for domains/crypto_coin/research/autonomous_exposure_control.py.

AutonomousExposureControl.control() previously referenced an undefined name
`fleet_mode` when building each decision's justification (it should have used
the locally computed `fleet_control_mode`), raising NameError for any call
with at least one strategy. This test exercises that exact code path with the
heavy analytics dependencies mocked out, so it fails with NameError against
the pre-fix code and passes once fleet_control_mode is used correctly.
"""

from types import SimpleNamespace
from unittest.mock import patch

from domains.crypto_coin.research.autonomous_exposure_control import (
    AutonomousExposureControl,
)


def test_control_builds_justification_without_undefined_name(tmp_path):
    fake_drift_report = SimpleNamespace(market_drift_score=10.0, fleet_health_avg=90.0)

    fake_strategy = SimpleNamespace(
        strategy_id="test_strategy",
        composite_risk=20.0,
        fragility_score=15.0,
        max_exposure_fraction=0.5,
    )
    fake_base_report = SimpleNamespace(strategies=[fake_strategy])

    with (
        patch(
            "domains.crypto_coin.research.autonomous_exposure_control.MarketDriftIntelligence"
        ) as MockDrift,
        patch(
            "domains.crypto_coin.research.autonomous_exposure_control.AdaptiveExposureIntelligence"
        ) as MockAdaptive,
        patch(
            "domains.crypto_coin.research.autonomous_exposure_control.DegradationFleetAnalyzer"
        ) as MockFleet,
        patch(
            "domains.crypto_coin.research.autonomous_exposure_control.StrategyActivationEngine"
        ) as MockActivation,
    ):
        MockDrift.return_value.analyze.return_value = fake_drift_report
        MockAdaptive.return_value.analyze.return_value = fake_base_report
        MockFleet.return_value.rank_all.return_value = [
            SimpleNamespace(strategy_id="test_strategy", composite_risk_score=20.0)
        ]
        MockActivation.return_value.evaluate.return_value = SimpleNamespace(
            activation_state="active"
        )

        controller = AutonomousExposureControl(
            experiments_dir=tmp_path,
            control_log=tmp_path / "exposure_control_log.jsonl",
        )

        report = controller.control(["test_strategy"])

    assert report.fleet_control_mode == "normal"
    assert len(report.decisions) == 1

    decision = report.decisions[0]
    assert decision.strategy_id == "test_strategy"
    assert decision.justification.startswith("fleet_mode=normal")
