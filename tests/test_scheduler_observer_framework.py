from __future__ import annotations

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from core.config import settings
from scheduler import service

JOB_ID = "platform:observer_framework_cycle"


def _noop_boot_heartbeat() -> None:
    return None


def _sqlalchemy_jobstore(tmp_path):
    return {"default": SQLAlchemyJobStore(url=f"sqlite:///{tmp_path / 'scheduler_jobs.sqlite'}")}


def _shutdown_scheduler(scheduler) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def test_observer_cycle_job_absent_when_schedule_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "boot_heartbeat", _noop_boot_heartbeat)
    monkeypatch.setattr(settings, "observer_framework_schedule_enabled", False)

    scheduler = service.create_scheduler(
        jobstores=_sqlalchemy_jobstore(tmp_path),
        start_paused_for_persistence=True,
    )
    try:
        assert scheduler.get_job(JOB_ID) is None
    finally:
        _shutdown_scheduler(scheduler)


def test_observer_cycle_job_registered_when_schedule_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "boot_heartbeat", _noop_boot_heartbeat)
    monkeypatch.setattr(settings, "observer_framework_enabled", True)
    monkeypatch.setattr(settings, "observer_framework_schedule_enabled", True)

    scheduler = service.create_scheduler(
        jobstores=_sqlalchemy_jobstore(tmp_path),
        start_paused_for_persistence=True,
    )
    try:
        job = scheduler.get_job(JOB_ID)
        assert job is not None
        assert "<lambda>" not in job.func_ref
        assert "<locals>" not in job.func_ref
    finally:
        _shutdown_scheduler(scheduler)


def test_observer_cycle_job_absent_when_master_switch_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "boot_heartbeat", _noop_boot_heartbeat)
    monkeypatch.setattr(settings, "observer_framework_enabled", False)
    monkeypatch.setattr(settings, "observer_framework_schedule_enabled", True)

    scheduler = service.create_scheduler(
        jobstores=_sqlalchemy_jobstore(tmp_path),
        start_paused_for_persistence=True,
    )
    try:
        assert scheduler.get_job(JOB_ID) is None
    finally:
        _shutdown_scheduler(scheduler)
