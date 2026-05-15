param(
  [string]$Module = "ecommerce",
  [string]$Source,
  [string]$CollectorName = "poupi_legacy_raw_collector",
  [int]$Limit = 500,
  [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

$query = @("limit=$Limit")
if ($Module) { $query += "module=$([uri]::EscapeDataString($Module))" }
if ($Source) { $query += "source_name=$([uri]::EscapeDataString($Source))" }
if ($CollectorName) { $query += "collector_name=$([uri]::EscapeDataString($CollectorName))" }

$url = "$ApiUrl/api/v1/operations/candidate-targets?$($query -join '&')"
Invoke-RestMethod $url | ConvertTo-Json -Depth 12
