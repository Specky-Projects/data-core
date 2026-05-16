# Documentation Synchronization Rules

> Mandatory for all AI agents working on this codebase. Updated: 2026-05-16.

---

## Rule: Every relevant change triggers doc sync

Whenever any of the following changes:

- Architecture or runtime topology
- Pipeline stages, jobs, schedules
- API endpoints (added, removed, changed)
- Scrapers or collectors
- Database schema or migrations
- Operational flows or deployment procedures
- Observability (metrics, alerts, logs, health checks)
- Deployment configuration

The AI **must automatically update** — without waiting for explicit instruction:

1. Relevant `/docs/*.md` file(s)
2. `ai/CONTEXT.md` (if architecture/topology/known gaps changed)
3. `README.md` (if setup, architecture overview, or endpoints changed)
4. `AGENTS.md` (if coding rules or constraints changed)

---

## Responsibility split

### `/docs/` — Human + AI readable

Full documentation for humans: onboarding, architecture, operation, troubleshooting.

| File | Owner topic |
|---|---|
| `DATA_FLOW.md` | ETL stages per domain |
| `JOBS_AND_SCHEDULES.md` | All scheduler jobs and triggers |
| `API_ENDPOINTS.md` | REST endpoints with request/response examples |
| `OBSERVABILITY.md` | Metrics, alerts, logs, health checks, SQL queries |
| `AUDIT.md` | Current audit: gaps, priorities, scale risks |

### `/ai/` — AI-optimized operational context

Dense context for autonomous AI agents.

| File | Content |
|---|---|
| `CONTEXT.md` | Full current state: topology, tables, files, gaps |
| `RUNBOOK.md` | Step-by-step: diagnose, deploy, fix, activate |
| `DOC_SYNC_RULES.md` | This file |

### `README.md` — Human onboarding

Project overview, architecture diagram, quick-start, environment variables, container roles.

### `AGENTS.md` — Coding rules

Architecture constraints, where to put code, migration rules, patterns.

---

## Anti-duplication rule

- `/ai/CONTEXT.md` references `/docs/*.md` — does NOT duplicate full content
- `/docs/*.md` files are the single source of truth for their topic
- `README.md` gives overview only — links to `/docs/` for details
- `AGENTS.md` focuses on coding constraints — not operational procedures

---

## End-of-phase checklist

Before closing any implementation phase:

```
[ ] All changed files have corresponding doc updates
[ ] /docs/* describes current reality (not past state)
[ ] ai/CONTEXT.md §Known gaps reflects new state
[ ] README.md quick-start and endpoint list are current
[ ] AGENTS.md rules match current architecture
[ ] No file references old container names, old endpoints, old schemas
[ ] Examples in docs can actually be run against production
```

---

## What "relevant change" means

**Relevant** (must sync):
- New endpoint added or removed
- New migration created
- New container role or env var
- Job schedule changed
- New Prometheus metric added
- Circuit breaker behavior changed
- New domain activated

**Not relevant** (no sync needed):
- Bug fix with no behavioral change
- Internal refactor with same interface
- Log message text changes
- Comment updates
