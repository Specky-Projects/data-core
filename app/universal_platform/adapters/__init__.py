"""Universal Adapter Layer — one adapter per project, all read-only.

Adapters are the *only* way a project reaches the Scientific Runtime. They
never touch a source system, never alter an engine, and always run in
SHADOW / READ_ONLY / ADVISORY_ONLY mode.
"""
from __future__ import annotations

from app.universal_platform.adapters.affiliate_adapter import AffiliateAdapter
from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.adapters.infrastructure_adapter import InfrastructureAdapter
from app.universal_platform.adapters.poupi_baby_adapter import PoupiBabyAdapter
from app.universal_platform.adapters.telegram_adapter import TelegramAdapter

__all__ = [
    "BaseAdapter",
    "PoupiBabyAdapter",
    "InfrastructureAdapter",
    "TelegramAdapter",
    "AffiliateAdapter",
]
