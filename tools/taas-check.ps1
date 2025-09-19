param(
  [string]$Url = "https://store.ratemate.top/login",
  [string]$Site = "",
  [string]$Api = "http://localhost:8000",
  [string]$ApiKey = "dev-key",
  [switch]$Perf,
  [switch]$Sec,
  [switch]$OpenReports
)

function Invoke-Json($method, $path, $body) {
  $headers = @{ 'x-api-key' = $ApiKey }
  if ($method -ieq 'POST') {
    return Invoke-RestMethod -Method Post "$Api$path" -Headers $headers -ContentType 'application/json' -Body $body
  } else {
    return Invoke-RestMethod "$Api$path" -Headers $headers
  }
}

function Enqueue-Web($type) {
  $payload = @{ test_type = $type }
  if ($Site) { $payload.site = $Site }
  if ($Url -and -not $Site) { $payload.url = $Url }
  $json = ($payload | ConvertTo-Json -Compress)
  return Invoke-Json 'POST' '/api/test/web' $json
}

function Poll-Job($jobId) {
  do {
    Start-Sleep 2
    $s = Invoke-Json 'GET' ("/api/jobs/$jobId") $null
    Write-Host ("status = {0}" -f $s.status)
  } while ($s.status -in @('queued','running'))
  return $s
}

function Show-Result($jobId, $OpenReports) {
  $base = Join-Path (Join-Path (Get-Location) 'test-results/taas') $jobId
  $jsonPath = "$base-result.json"
  if (Test-Path $jsonPath) {
    Write-Host "Result JSON: $jsonPath"
    Get-Content $jsonPath
  } else {
    Write-Host "Result JSON not found: $jsonPath" -ForegroundColor Yellow
  }
  if ($OpenReports) {
    foreach ($ext in @('perf.html','zap.html','-1-screenshot.png')) {
      $p = "$base-$ext"
      if (Test-Path $p) { Invoke-Item $p }
    }
  }
}

try {
  $health = Invoke-Json 'GET' '/healthz' $null
  if (-not $health.ok) { Write-Error "API not healthy: $($health | ConvertTo-Json -Compress)"; exit 2 }
} catch {
  Write-Error "Cannot reach API at $Api. Start stack: docker compose -f docker-compose.taas.yml up -d"
  exit 2
}

if (-not $Perf -and -not $Sec) { $Perf = $true; $Sec = $true }

if ($Perf) {
  Write-Host "=== Performance (Lighthouse) ===" -ForegroundColor Cyan
  $resp = Enqueue-Web 'performance'
  $job = $resp.job_id
  Write-Host "job_id=$job"
  $final = Poll-Job $job
  Show-Result $job $OpenReports
}

if ($Sec) {
  Write-Host "=== Security (OWASP ZAP) ===" -ForegroundColor Cyan
  $resp = Enqueue-Web 'security'
  $job = $resp.job_id
  Write-Host "job_id=$job"
  $final = Poll-Job $job
  Show-Result $job $OpenReports
}

