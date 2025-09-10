Param(
  [string]$Message = "chore: sync",
  [switch]$NoAdd,
  [switch]$NoSubmodule,
  [switch]$NoFixRemotes,
  [switch]$Mirror,
  [string]$BitBranch,
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

# --- Optional: normalize remotes so origin has single push-URL (GitHub) and Bitbucket is its own remote
if (-not $NoFixRemotes) {
  $originFetch = (& git remote get-url origin 2>$null).Trim()
  $originPushAll = (& git remote get-url --push origin --all 2>$null)
  if ($originPushAll) {
    $pushUrls = @()
    foreach ($line in ($originPushAll -split "`n")) { if ($line.Trim()) { $pushUrls += $line.Trim() } }
    $distinct = $pushUrls | Select-Object -Unique
    if ($distinct.Count -gt 1) {
      foreach ($u in $distinct) {
        if ($u -ne $originFetch) {
          # Treat non-fetch URL as secondary (likely Bitbucket). Ensure separate 'bitbucket' remote.
          $bbExisting = (& git remote get-url bitbucket 2>$null)
          if (-not $bbExisting) {
            Write-Host "Creating 'bitbucket' remote -> $u" -ForegroundColor Yellow
            TryRun @('remote','add','bitbucket',$u)
          }
          Write-Host "Detaching extra push-URL from 'origin' -> $u" -ForegroundColor Yellow
          TryRun @('remote','set-url','--delete','--push','origin',$u)
        }
      }
    }
  }
}

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

# Robust push logic: prefer origin (fetch URL), fall back if origin push-URLs fail
$hasUpstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
$originFetch = (& git remote get-url origin 2>$null).Trim()
if (-not $originFetch) { throw "Remote 'origin' is not configured" }

if (-not $hasUpstream) {
  Write-Host "Setting upstream to origin/$current" -ForegroundColor Yellow
  try {
    Run @('push','-u','origin',$current)
  } catch {
    Write-Warning "Push to origin failed (likely due to multiple push-URLs). Falling back to fetch URL only."
    # Push directly to fetch URL, then set upstream manually
    Run @('push',$originFetch,$current)
    TryRun @('branch','--set-upstream-to="origin/'+$current+'"',$current)
  }
} else {
  try {
    Run @('push','origin',$current)
  } catch {
    Write-Warning "Push to origin failed; trying fetch URL only."
    Run @('push',$originFetch,$current)
  }
}

# Also push to 'bitbucket' remote if present (explicit), ignore errors
$bbUrl = (& git remote get-url bitbucket 2>$null)
if ($bbUrl) {
  if ($Mirror) {
    Write-Host "Mirroring to bitbucket (branches/tags, prune)" -ForegroundColor Yellow
    TryRun @('push','--mirror','--prune','bitbucket')
  } else {
    Write-Host "Pushing to bitbucket remote as well" -ForegroundColor Yellow
    if ([string]::IsNullOrWhiteSpace($BitBranch)) {
      TryRun @('push','bitbucket',$current)
    } else {
      # Push current HEAD to a specific branch name on Bitbucket
      TryRun @('push','bitbucket',"${current}:${BitBranch}")
    }
  }
} else {
  # If origin had extra push-URLs, recommend using separate 'bitbucket' remote
  $originPushAll = (& git remote get-url --push origin --all 2>$null)
  if ($originPushAll -and ($originPushAll -split "`n").Count -gt 1) {
    Write-Warning "Detected multiple push-URLs in 'origin'. Consider: `n  git remote set-url --delete --push origin <bitbucket-url>`n  git remote add bitbucket <bitbucket-url>"
  }
}

Write-Host "\nAll done." -ForegroundColor Green
