param()

$ErrorActionPreference = 'Stop'
$WORKTREE = $env:WORKTREE_PATH
$REPO    = $env:REPO_PATH

if (-not $WORKTREE -or -not (Test-Path $WORKTREE)) {
    Write-Host "ERROR: WORKTREE_PATH is not set or invalid."
    exit 1
}

Set-Location -LiteralPath $WORKTREE

$VENV_DIR = Join-Path $WORKTREE ".venv"
$PYTHON   = Join-Path $VENV_DIR "Scripts\python.exe"

if (-not (Test-Path $PYTHON)) {
    Write-Host "ERROR: Virtual environment not found. Run setup first."
    exit 1
}

Write-Host "==> Starting Backlot server..."
Write-Host "    Project root: $WORKTREE"
Write-Host "    Press Ctrl+C to stop."
Write-Host ""

& $PYTHON -m backlot serve
