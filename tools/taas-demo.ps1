param(
  [string]$Url = "https://store.ratemate.top",
  [string]$Site = "",
  [ValidateSet("auto","smoke")] [string]$TestType = "auto",
  [string]$Api = "http://localhost:8000",
  [string]$ApiKey = "dev-key"
)

Write-Host "Enqueue web test ($TestType) ..."
$body = if ($Site) { @{ site = $Site; test_type = $TestType } } else { @{ url = $Url; test_type = $TestType } }
$json = $body | ConvertTo-Json -Compress
$resp = Invoke-RestMethod -Method Post "$Api/api/test/web" -Headers @{ 'x-api-key'=$ApiKey } -ContentType 'application/json' -Body $json
$id = $resp.job_id
Write-Host "job_id = $id"

Write-Host "Polling status ..."
do {
  Start-Sleep -Seconds 1
  $s = Invoke-RestMethod "$Api/api/jobs/$id" -Headers @{ 'x-api-key'=$ApiKey }
  Write-Host ("status = {0}" -f $s.status)
} while ($s.status -in @('queued','running'))

$result = Join-Path (Join-Path (Get-Location) 'test-results/taas') "$id-result.json"
if (Test-Path $result) {
  Write-Host "Result: $result"
  Get-Content $result
}

$png = Join-Path (Join-Path (Get-Location) 'test-results/taas') "$id-1-screenshot.png"
if (Test-Path $png) { Invoke-Item $png }
