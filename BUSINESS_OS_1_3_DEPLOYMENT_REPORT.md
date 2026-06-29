# BUSINESS OS 1.3 — DEPLOYMENT REPORT

**Date:** 2026-06-29
**Environment:** COOLIFY / VPS 65.109.239.250
**Container:** `fe4b6ef995be_dvq6dwsagsw4p4oqwuw7bak9-api-1`
**Final commit:** `33bb8a8`

---

## Deployment Summary

Business OS 1.3 Stage 4 is running in production.

One blocker was encountered and resolved during deployment. No application logic was changed.

---

## Deployment Sequence

### Step 1 — VPS Remote URL Mismatch

**Finding:** The Coolify app directory (`/data/coolify/applications/dvq6dwsagsw4p4oqwuw7bak9/`) had remote `https://github.com/poupi-hub/data-core.git`. After the GitHub repo transfer to `Specky-Projects`, this remote was stale and did not see Stage 4 commits.

**Action:** `git remote set-url origin https://github.com/Specky-Projects/data-core.git`

**Result:** All commits through `1f18718` became visible. Category: **CONFIGURATION**

---

### Step 2 — History Divergence

**Finding:** VPS was at `57bdb11`. Origin had a diverged history (commits rewritten during repo transfer with same messages but different hashes). `git pull` failed with "divergent branches".

**Action:** `git reset --hard origin/main` → VPS at `1f18718`

**Result:** VPS fully aligned to certified repository. Category: **REPOSITORY**

---

### Step 3 — FastAPI Python 3.11 Startup Failure

**Finding:** Container restarted and crashed immediately with:

```
AssertionError: `Query` default value cannot be set in `Annotated` for 'lookback_days'.
Set the default value with `=` instead.
```

**Root Cause:** FastAPI 0.115.0 on Python 3.11 rejects `Query(default=X)` inside `Annotated` type aliases. The same FastAPI version on Python 3.12 (local dev) silently accepts it. The assertion is in `fastapi/dependencies/utils.py:380`.

**Files affected:** `app/adaptive_intelligence/api.py` — 4 type aliases, 5 route functions.

**Category:** RUNTIME COMPATIBILITY

**Fix applied (commit `33bb8a8`):**

```python
# Before — rejected on Python 3.11:
LookbackDaysQuery = Annotated[int, Query(default=30, ge=1, le=180)]
def get_full_report(lookback_days: LookbackDaysQuery, ...):

# After — compatible with Python 3.11+:
LookbackDaysQuery = Annotated[int, Query(ge=1, le=180)]
def get_full_report(lookback_days: LookbackDaysQuery = 30, ...):
```

All 5 endpoints updated. Behavior is identical. 203/203 tests pass after fix.

---

### Step 4 — Deploy Success

**Action:** `git pull origin main` (fetched `33bb8a8`) + `docker compose restart api`

**Container health:** `healthy` (Docker healthcheck passed)

**Startup logs:**
```
INFO: Started server process [7]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

No errors. No import failures. No assertion errors.

---

## Container State

| Property | Value |
|----------|-------|
| Container | `fe4b6ef995be_dvq6dwsagsw4p4oqwuw7bak9-api-1` |
| Image | `data-core-api-light` (volume-mounted source code) |
| Running commit | `33bb8a8` |
| Python | 3.11.15 |
| FastAPI | 0.115.0 |
| Pydantic | 2.9.2 |
| Health status | healthy |
| Source mount | `/data/coolify/applications/dvq6dwsagsw4p4oqwuw7bak9:/app` |

---

## Deployment Architecture Note

The production deployment uses a **volume-mount pattern** rather than a build-and-bake pattern. The container image (`data-core-api-light`) is a base image with dependencies pre-installed. The application source code is mounted from `/data/coolify/applications/dvq6dwsagsw4p4oqwuw7bak9/` into the container at `/app`. Updates are applied by `git pull` + `docker compose restart`.

This means the running code exactly matches what is in the Coolify app directory, which after deployment is at commit `33bb8a8`.

---

## Deployment Verdict

```
DEPLOYMENT: COMPLETE
STATUS: PRODUCTION GO
COMMIT: 33bb8a8
PYTHON: 3.11.15
CONTAINER: healthy
```
