param(
  [Parameter(Position=0)] [string]$Target = "help",
  [string]$SITE,
  [string]$URL,
  [switch]$AllowWrite
)

function Build {
  docker build -t ratemate-tests .
}

function RunFull {
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  mkdir report -ErrorAction SilentlyContinue | Out-Null
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "pytest -vv -p pytest_playwright -p pytest_html tests/auth tests/smoke/test_routes.py `
      --browser=chromium --browser=webkit `
      --screenshot=only-on-failure --video=off --tracing=retain-on-failure `
      --excelreport=report/run-$ts.xlsx `
      --junitxml=report/junit-$ts.xml `
      --html=report/report-$ts.html --self-contained-html `
      -o cache_dir=/tmp/pytest_cache --output=/tmp/test-results `
      --reruns 1 --reruns-delay 1"
}

function Smoke {
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  mkdir report -ErrorAction SilentlyContinue | Out-Null
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "pytest -vv -p pytest_playwright -p pytest_html tests/smoke/test_routes.py `
      --browser=chromium --browser=webkit `
      --screenshot=only-on-failure --video=off --tracing=retain-on-failure `
      --excelreport=report/smoke-$ts.xlsx `
      --junitxml=report/junit-$ts.xml `
      --html=report/report-$ts.html --self-contained-html `
      -o cache_dir=/tmp/pytest_cache --output=/tmp/test-results `
      --reruns 1 --reruns-delay 1"
}

function Roles {
  if (-not $SITE) { Write-Host "Usage: .\make.ps1 roles -SITE <site>"; return }
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "SITE=$SITE pytest -vv -m roles tests --browser=chromium --screenshot=only-on-failure --tracing=retain-on-failure --reruns 1 --reruns-delay 1"
}

function WriteTests {
  if (-not $SITE) { Write-Host "Usage: .\make.ps1 write -SITE <site> [-AllowWrite]"; return }
  $allow = if ($AllowWrite) { "1" } else { "0" }
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "SITE=$SITE E2E_ALLOW_WRITE=$allow pytest -vv -m write tests --browser=chromium --screenshot=only-on-failure --tracing=retain-on-failure"
}

function Discover {
  if (-not $URL) { Write-Host "Usage: .\make.ps1 discover -URL https://host/login"; return }
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "python tools/discover_routes.py --url '$URL' --emit-tests --emit-yaml"
}

function SecretsCheck {
  $vars = @('E2E_PLATFORM_ADMIN_EMAIL','E2E_SUPER_ADMIN_EMAIL','E2E_MANAGER_EMAIL','E2E_STAFF_A_EMAIL','E2E_STAFF_B_EMAIL')
  foreach ($v in $vars) {
    if ($env:$v) { Write-Host "  $v=SET" } else { Write-Host "  $v=missing" }
  }
}

switch ($Target) {
  "build" { Build }
  "run"   { RunFull }
  "smoke" { Smoke }
  "roles" { Roles }
  "write" { WriteTests }
  "discover" { Discover }
  "secrets-check" { SecretsCheck }
  default { Write-Host "Usage: .\make.ps1 [build|run|smoke|roles|write|discover|secrets-check] [-SITE <site>] [-URL <url>]" }
}
