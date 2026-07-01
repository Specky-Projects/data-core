"""WS6 — Unified Daily Brief.

One consolidated report instead of many. Each section is produced from the
records emitted by the respective adapter, plus the alerts from the Unified
Alert Engine. The brief renders deterministically to Markdown for Telegram
delivery (render-only; the brief never triggers an action).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.scientific_identity.contract import stable_hash
from app.universal_platform.alert_engine import UnifiedAlert
from app.universal_platform.events import Severity
from app.universal_platform.runtime import UniversalObservationRecord

# Canonical section order of the unified brief.
SECTION_ORDER = (
    "Mirror",
    "Poupi Baby",
    "Infrastructure",
    "Research",
    "Affiliate",
    "Knowledge",
    "Optimization",
    "Open Alerts",
    "Top Opportunities",
    "Scientific Health",
    "Executive Summary",
)

# Adapter project -> brief section title.
_PROJECT_SECTION = {
    "mirror": "Mirror",
    "poupi-baby": "Poupi Baby",
    "infrastructure": "Infrastructure",
    "research": "Research",
    "affiliate": "Affiliate",
    "knowledge": "Knowledge",
    "optimization": "Optimization",
}


@dataclass(frozen=True)
class DailyBriefSection:
    title: str
    headline: str
    metrics: dict[str, Any] = field(default_factory=dict)
    lines: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "headline": self.headline,
            "metrics": self.metrics,
            "lines": list(self.lines),
        }


@dataclass(frozen=True)
class UnifiedDailyBrief:
    brief_id: str
    generated_at: str
    sections: tuple[DailyBriefSection, ...]
    scientific_health: float
    advisory_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "generated_at": self.generated_at,
            "scientific_health": self.scientific_health,
            "advisory_only": self.advisory_only,
            "sections": [s.as_dict() for s in self.sections],
        }

    def render_markdown(self) -> str:
        out = [f"# Business OS Daily — {self.generated_at}", ""]
        out.append(f"_Scientific Health: {self.scientific_health:.2%} · advisory-only_")
        out.append("")
        for section in self.sections:
            out.append(f"## {section.title}")
            out.append(section.headline)
            for line in section.lines:
                out.append(f"- {line}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"


def _section_for_records(
    title: str, records: list[UniversalObservationRecord]
) -> DailyBriefSection:
    if not records:
        return DailyBriefSection(title=title, headline="No activity observed.")
    by_type: dict[str, int] = {}
    coverage_sum = 0.0
    worst = Severity.INFO
    for r in records:
        by_type[r.event.event_type] = by_type.get(r.event.event_type, 0) + 1
        coverage_sum += r.coverage.coverage_ratio
        if r.severity.rank > worst.rank:
            worst = r.severity
    avg_cov = coverage_sum / len(records)
    lines = tuple(f"{etype}: {count}" for etype, count in sorted(by_type.items()))
    return DailyBriefSection(
        title=title,
        headline=f"{len(records)} observation(s), worst severity {worst.value}.",
        metrics={"count": len(records), "avg_coverage": round(avg_cov, 4), "worst_severity": worst.value},
        lines=lines,
    )


def _top_opportunities(records: list[UniversalObservationRecord], limit: int = 5) -> DailyBriefSection:
    candidates = [
        r for r in records if r.event.project in ("poupi-baby", "affiliate", "mirror")
    ]
    candidates.sort(key=lambda r: r.event.confidence, reverse=True)
    lines = tuple(
        f"[{r.event.project}] {r.event.entity_id} — confidence {r.event.confidence:.2f}"
        for r in candidates[:limit]
    )
    return DailyBriefSection(
        title="Top Opportunities",
        headline=f"{min(len(candidates), limit)} highest-confidence opportunit(ies).",
        lines=lines or ("None observed.",),
    )


def _open_alerts_section(alerts: list[UnifiedAlert]) -> DailyBriefSection:
    if not alerts:
        return DailyBriefSection(title="Open Alerts", headline="No open alerts.")
    lines = tuple(f"[{a.severity.value}] {a.title} — {a.recommended_action}" for a in alerts)
    return DailyBriefSection(
        title="Open Alerts",
        headline=f"{len(alerts)} open alert(s).",
        metrics={"count": len(alerts)},
        lines=lines,
    )


def _scientific_health(records: list[UniversalObservationRecord]) -> float:
    if not records:
        return 1.0
    complete = sum(1 for r in records if r.coverage.is_complete)
    return round(complete / len(records), 4)


class DailyBriefBuilder:
    ADVISORY_ONLY = True

    def build(
        self,
        records: list[UniversalObservationRecord],
        alerts: list[UnifiedAlert] | None = None,
        generated_at: str = "",
        extra_sections: dict[str, DailyBriefSection] | None = None,
    ) -> UnifiedDailyBrief:
        alerts = alerts or []
        extra_sections = extra_sections or {}

        by_project: dict[str, list[UniversalObservationRecord]] = {}
        for r in records:
            by_project.setdefault(r.event.project, []).append(r)

        health = _scientific_health(records)
        sections: list[DailyBriefSection] = []
        for title in SECTION_ORDER:
            if title in extra_sections:
                sections.append(extra_sections[title])
                continue
            if title == "Open Alerts":
                sections.append(_open_alerts_section(alerts))
            elif title == "Top Opportunities":
                sections.append(_top_opportunities(records))
            elif title == "Scientific Health":
                sections.append(
                    DailyBriefSection(
                        title="Scientific Health",
                        headline=f"{health:.2%} of observations fully covered.",
                        metrics={"health": health, "observations": len(records)},
                    )
                )
            elif title == "Executive Summary":
                sections.append(
                    DailyBriefSection(
                        title="Executive Summary",
                        headline=(
                            f"{len(records)} observation(s) across {len(by_project)} project(s); "
                            f"{len(alerts)} alert(s); scientific health {health:.2%}."
                        ),
                    )
                )
            else:
                project = next((p for p, t in _PROJECT_SECTION.items() if t == title), None)
                sections.append(_section_for_records(title, by_project.get(project or "", [])))

        return UnifiedDailyBrief(
            brief_id=stable_hash({"generated_at": generated_at, "count": len(records)}),
            generated_at=generated_at,
            sections=tuple(sections),
            scientific_health=health,
        )
