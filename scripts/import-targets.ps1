param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

$resolved = Resolve-Path -LiteralPath $Path
if ($resolved.Path.EndsWith(".csv")) {
  $targets = Import-Csv -LiteralPath $resolved.Path | ForEach-Object {
    $metadata = @{}
    if ($_.metadata_json) {
      $metadata = $_.metadata_json | ConvertFrom-Json
    }
    [pscustomobject]@{
      module = $_.module
      source_name = $_.source_name
      collector_name = $_.collector_name
      target_url = $_.target_url
      active = if ($_.active) { [System.Convert]::ToBoolean($_.active) } else { $true }
      metadata_json = $metadata
    }
  }
} else {
  $content = Get-Content -LiteralPath $resolved.Path -Raw
  $json = $content | ConvertFrom-Json
  $targets = if ($json.targets) { $json.targets } else { $json }
}

$body = @{ targets = @($targets) } | ConvertTo-Json -Depth 20
Invoke-RestMethod -Method Post -ContentType "application/json" -Body $body "$ApiUrl/api/v1/collection-targets/import" |
  ConvertTo-Json -Depth 20
