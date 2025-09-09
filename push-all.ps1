Param(
  [string]$Message = "chore: sync",
  [switch]$NoAdd,
  [switch]$NoSubmodule,
  [string]$Branch
)

# NOTE: do NOT use parameter name `$args`/`$Args` because it's a PS automatic var
function Run([string[]]$Cmd) {
  Write-Host "`n> git $($Cmd -join ' ')" -ForegroundColor Cyan
  & git @Cmd
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Cmd -join ' ') failed with exit code $LASTEXITCODE"
  }
}

function TryRun([string[]]$Cmd) {
  Write-Host "`n> git $($Cmd -join ' ')" -ForegroundColor DarkCyan
  & git @Cmd
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "git $($Cmd -join ' ') returned $LASTEXITCODE (ignored)"
  }
}

if (-not (Test-Path ".git")) {
  throw "This directory is not a git repository. Run inside your repo root."
}

# Detect branch
$current = if ($Branch) { $Branch } else { (& git rev-parse --abbrev-ref HEAD).Trim() }
if (-not $current) { throw "Cannot determine current branch." }
Write-Host "Current branch: $current" -ForegroundColor Green

# Optionally stage changes in parent repo
if (-not $NoAdd) {
  TryRun @('add','-A')
}

# Handle submodules first so parent pointer can be committed afterwards
if (-not $NoSubmodule -and (Test-Path ".gitmodules")) {
  Write-Host "Processing submodules..." -ForegroundColor Yellow
  $paths = & git config -f .gitmodules --get-regexp 'submodule\..*\.path' 2>$null |
    ForEach-Object { ($_ -split '\s+',2)[1] }
  foreach ($p in $paths) {
    if (-not (Test-Path $p)) { continue }
    Push-Location $p
    try {
      Write-Host "Submodule: $p" -ForegroundColor Yellow
      # Stage changes in submodule
      TryRun @('add','-A')
      # Commit if anything staged
      & git diff --cached --quiet
      if ($LASTEXITCODE -ne 0) {
        Run @('commit','-m',$Message)
      } else {
        Write-Host "No staged changes in submodule $p" -ForegroundColor DarkGray
      }

      # Push submodule
      $upstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
      if ($upstream) {
        Run @('push')
      } else {
        # Default to origin HEAD if no upstream
        TryRun @('remote','get-url','origin')
        Run @('push','-u','origin','HEAD')
      }
    } finally {
      Pop-Location
    }
  }
  # Stage updated submodule pointers in parent
  TryRun @('add','-A')
}

# Commit in parent if any staged changes
& git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  Run @('commit','-m',$Message)
} else {
  Write-Host "No staged changes to commit in parent repo" -ForegroundColor DarkGray
}

# Ensure upstream
$hasUpstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
if (-not $hasUpstream) {
  Write-Host "Setting upstream to origin/$current" -ForegroundColor Yellow
  Run @('push','-u','origin',$current)
} else {
  # Push to origin (may include multiple push-URLs)
  Run @('push','origin',$current)
}

# Also push to 'bitbucket' remote if present (explicit)
$bbUrl = (& git remote get-url bitbucket 2>$null)
if ($bbUrl) {
  Write-Host "Pushing to bitbucket remote as well" -ForegroundColor Yellow
  TryRun @('push','bitbucket',$current)
}

Write-Host "\nAll done." -ForegroundColor Green
