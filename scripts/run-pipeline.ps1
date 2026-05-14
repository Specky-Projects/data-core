param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("ecommerce", "real_estate", "sports_odds", "crypto", "trading")]
  [string]$Module,

  [string]$Source,
  [switch]$SkipNormalize,
  [switch]$SkipAnalytics
)

$ErrorActionPreference = "Stop"

$argsList = @("python", "-m", "app.jobs.run", "--module", $Module)
if ($Source) {
  $argsList += @("--source", $Source)
}
if ($SkipNormalize) {
  $argsList += "--skip-normalize"
}
if ($SkipAnalytics) {
  $argsList += "--skip-analytics"
}

docker compose exec -T api @argsList
