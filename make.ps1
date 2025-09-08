param([Parameter(Position=0)] [string]$Target = "help")

function Build {
  docker build -t ratemate-tests .
}
function RunFull {
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  mkdir report -ErrorAction SilentlyContinue | Out-Null
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "pytest -vv -p pytest_playwright -p pytest_html tests/auth tests/smoke/test_routes.py -p no:pytest_excel --browser=chromium --browser=webkit --screenshot=only-on-failure --video=off --tracing=retain-on-failure --excelreport=report/run-$ts.xlsx -o cache_dir=/tmp/pytest_cache --output=/tmp/test-results"
}
function Smoke {
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  mkdir report -ErrorAction SilentlyContinue | Out-Null
  docker run --rm -t --ipc=host --shm-size=1g `
    -v "${PWD}:/app" --env-file .env ratemate-tests bash -lc `
    "pytest -vv -p pytest_playwright -p pytest_html tests/smoke/test_routes.py -p no:pytest_excel --browser=chromium --browser=webkit --screenshot=only-on-failure --video=off --tracing=retain-on-failure --excelreport=report/smoke-$ts.xlsx -o cache_dir=/tmp/pytest_cache --output=/tmp/test-results"
}

switch ($Target) {
  "build" { Build }
  "run"   { RunFull }
  "smoke" { Smoke }
  default { Write-Host "Usage: .\make.ps1 [build|run|smoke]" }
}
