param(
  [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "Health"
Invoke-RestMethod "$ApiUrl/health" | ConvertTo-Json -Depth 8

Write-Host "`nOperations summary"
$summary = Invoke-RestMethod "$ApiUrl/api/v1/operations/summary"
[pscustomobject]@{
  raw_pending_by_module = $summary.raw_pending_by_module
  raw_failed_by_module = $summary.raw_failed_by_module
  analytics_pending_by_module = $summary.analytics_pending_by_module
  recent_collector_errors_count = @($summary.recent_collector_errors).Count
} | ConvertTo-Json -Depth 8

Write-Host "`nFreshness"
$freshness = Invoke-RestMethod "$ApiUrl/api/v1/operations/freshness"
[pscustomobject]@{
  generated_at = $freshness.generated_at
  summary = $freshness.summary
  stale_or_unknown = @($freshness.items | Where-Object { $_.status -ne "ok" } | Select-Object -First 20)
} | ConvertTo-Json -Depth 8
