# data-core — AI Runbook

> For AI agents executing operational tasks autonomously. Updated: 2026-05-16.
> Pre-read: `ai/CONTEXT.md`

---

## 1. Diagnose pipeline issue

```bash
# Step 1 — is API up?
curl http://data-core-api:8000/live
# expects: {"status":"alive","app":"data-core"}

# Step 2 — dependencies healthy?
curl http://data-core-api:8000/ready
# expects: {"ready":true,"checks":{"postgres":"ok","redis":"ok"}}

# Step 3 — recent failures (last 24h)?
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT domain, stage, error_type, LEFT(error_message, 100), occurred_at
FROM pipeline_failures
WHERE occurred_at > NOW() - INTERVAL '24 hours'
ORDER BY occurred_at DESC LIMIT 10;"

# Step 4 — recent runs (all domains)?
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT domain, stage, status, ROUND(duration_seconds::numeric,2) dur_s, items_processed, started_at
FROM pipeline_runs ORDER BY started_at DESC LIMIT 20;"

# Step 5 — stuck runs (running > 30 min)?
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT domain, stage, status, started_at FROM pipeline_runs
WHERE status='running' AND started_at < NOW() - INTERVAL '30 min';"

# Step 6 — circuit breakers open?
curl http://data-core-api:8000/api/v1/operations/alerts | python3 -c "import sys,json; a=json.load(sys.stdin); print('CB:', a.get('circuit_breakers')); print('DL:', a.get('dead_letters'))"

# Step 7 — raw data accumulating?
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT module, processing_status, COUNT(*) FROM raw_collections
GROUP BY module, processing_status ORDER BY module, processing_status;"

# Step 8 — crypto collection recent?
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT COUNT(*), MAX(collected_at) FROM raw_collections WHERE module='crypto';"
```

---

## 2. Deploy a code change

```bash
# On local machine:
cd /path/to/data-core
git add <files>
git commit -m "feat: description"
git push origin main

# On server — trigger Coolify build:
ssh poupi "
python3 -c \"
import json, subprocess, uuid

# Create deploy payload
deploy_uuid = str(uuid.uuid4())
result = subprocess.run([
    'docker', 'exec', '-i',
    'coolify-db-container',  # replace with actual name
    'psql', '-U', 'coolify', '-d', 'coolify', '-c',
    f\\\"INSERT INTO application_deployment_queues (application_id, deployment_uuid, force_rebuild, commit, status, is_api, server_id, application_name, server_name, destination_id, created_at, updated_at) VALUES ('1', '{deploy_uuid}', true, 'HEAD', 'queued', true, 0, 'data-core', 'coolify', '0', NOW(), NOW());\\\"
], capture_output=True)
print(result.stdout.decode())
\"
"

# Simpler: use the PHP trigger script approach from session history
# See: ai/CONTEXT.md §Deployment for full procedure
```

**Monitor deployment:**
```bash
ssh poupi "docker exec -i \$(docker ps -q --filter name=coolify-db) psql -U coolify -d coolify -c \"SELECT id, status, finished_at FROM application_deployment_queues ORDER BY id DESC LIMIT 3;\""
```

**Verify deployment succeeded:**
```bash
# New containers should show new commit hash
ssh poupi "docker ps --format '{{.Names}}\t{{.Image}}' | grep dvq6"

# Check migration is current
ssh poupi "docker exec \$(docker ps -q --filter name=api-dvq) alembic current"

# Check health
ssh poupi "API_IP=\$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \$(docker ps -q --filter name=api-dvq) | awk '{print \$1}'); curl -s http://\$API_IP:8000/ready"
```

---

## 3. Run a migration

Migrations run automatically when the API container starts (`alembic upgrade head` in CMD).

**To create a new migration:**
```bash
# Local:
cd data-core
alembic revision --autogenerate -m "short_description"
# IMPORTANT: revision ID must be <= 32 chars (alembic_version varchar(32) constraint)
# Edit the generated file to set a short revision id, e.g. "0016_short_name"

# Add down_revision = "0015_pipeline_observability"
# Commit and push → deploy triggers migration automatically
```

**Migration history:**
```
0015_pipeline_observability  ← HEAD (pipeline_runs, pipeline_failures)
0014_uniq_candle_identity    (UNIQUE on normalized_market_candles)
0013_...                     (earlier migrations)
```

---

## 4. Activate a domain collector

### Ecommerce (Drogasil scraper)
```sql
-- Add real product URLs to collection_targets:
INSERT INTO collection_targets (module, source_name, target_url, is_active, scrape_interval_minutes)
VALUES ('ecommerce', 'drogasil', 'https://www.drogasil.com.br/category/...', true, 60);
```

### Sports odds
```bash
# Set THE_ODDS_API_KEY via Coolify env vars, then redeploy
# API: PATCH http://coolify-host:8000/api/v1/applications/dvq6dwsagsw4p4oqwuw7bak9/envs
# Body: {"key": "THE_ODDS_API_KEY", "value": "your-key-here"}
```

### Real estate (Apolar)
```python
# In scheduler/jobs.py, register ApolarCollector with real city params
# Collector exists at: collectors/real_estate/apolar.py
```

---

## 5. Reset a circuit breaker

```python
# A source is deactivated after 5 consecutive failures.
# To manually reset:
from scheduler.circuit_breaker import reopen_source_circuit
reopen_source_circuit(module="crypto", source_name="binance")
```

Or via psql:
```sql
-- Reactivate target:
UPDATE collection_targets SET is_active = true WHERE source_name = 'binance';

-- Mark circuit breaker error as resolved:
UPDATE collector_errors SET resolved_at = NOW()
WHERE error_type = 'CircuitOpen' AND resolved_at IS NULL AND module = 'crypto';
```

---

## 6. Check crypto data quality

```bash
# Candles count per symbol/timeframe:
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT symbol, timeframe, COUNT(*), MAX(timestamp) as latest
FROM normalized_market_candles
GROUP BY symbol, timeframe ORDER BY symbol, timeframe;"

# Analytics count and latest signals:
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT symbol, timeframe, signal, confidence, regime, calculated_at
FROM trading_analytics
ORDER BY calculated_at DESC LIMIT 10;"

# Data lineage check:
docker exec multi_project_infra-postgres-1 psql -U data_core_user -d data_core_db -c "
SELECT COUNT(*) as raw, 
  (SELECT COUNT(*) FROM normalized_market_candles) as normalized,
  (SELECT COUNT(*) FROM trading_analytics) as analytics
FROM raw_collections WHERE module='crypto';"
```

---

## 7. Update Grafana dashboard

```bash
# Import updated dashboard to production:
scp docs/grafana-dashboard-data-core-ops.json poupi:/tmp/dashboard.json
ssh poupi "python3 -c \"
import json
with open('/tmp/dashboard.json') as f:
    dash = json.load(f)
payload = {'dashboard': dash, 'overwrite': True, 'folderId': 0}
with open('/tmp/import_payload.json', 'w') as f:
    json.dump(payload, f)
\"
curl -s -X POST \
  -u admin:GRAFANA_PASS \
  -H 'Content-Type: application/json' \
  -d @/tmp/import_payload.json \
  http://10.0.2.7:3000/api/dashboards/import"
```

---

## 8. Documentation sync (mandatory after any change)

After any change to architecture, endpoints, pipeline, schema, jobs, or observability:

1. Update implementation
2. Update relevant `/docs/*.md` file(s)
3. Update `ai/CONTEXT.md` if architecture/topology/gaps changed
4. Update `README.md` if setup or endpoints changed
5. Update `AGENTS.md` if coding rules or constraints changed
6. Run this verification:

```
Checklist:
[ ] /docs/* reflects current reality
[ ] ai/CONTEXT.md reflects current runtime state
[ ] README.md quick-start works
[ ] AGENTS.md rules are accurate
[ ] No examples reference deleted endpoints or old container names
```

Reference: `ai/DOC_SYNC_RULES.md`

---

## 9. Container name pattern

Container names change on every deploy: `{service}-dvq6dwsagsw4p4oqwuw7bak9-{timestamp}`

**Find current containers:**
```bash
ssh poupi "docker ps --format '{{.Names}}\t{{.Status}}' | grep dvq6"
```

**Get API IP:**
```bash
ssh poupi "docker inspect \$(docker ps -q --filter name=api-dvq6) --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'"
```

**Network alias is stable:** `data-core-api` on `coolify` network. Use this for internal calls.
