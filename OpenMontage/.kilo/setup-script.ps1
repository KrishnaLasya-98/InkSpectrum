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
$PIP      = Join-Path $VENV_DIR "Scripts\pip.exe"

# 1) Ensure venv exists
if (-not (Test-Path $PYTHON)) {
    Write-Host "==> Creating virtual environment (.venv)..."
    python -m venv $VENV_DIR
    if (-not (Test-Path $PYTHON)) {
        Write-Host "ERROR: Failed to create virtual environment."
        exit 1
    }
} else {
    Write-Host "==> Using existing virtual environment: $VENV_DIR"
}

# 2) Install Python dependencies
Write-Host "==> Installing Python dependencies..."
& $PIP install -r (Join-Path $REPO "requirements.txt")

# 3) Install Remotion composer deps (optional)
$remotionDir = Join-Path $WORKTREE "remotion-composer"
if (Test-Path $remotionDir) {
    Write-Host "==> Installing Remotion composer dependencies..."
    Push-Location $remotionDir
    try {
        npm install
    } catch {
        Write-Host "  [warn] npm install failed in remotion-composer — continuing."
    }
    Pop-Location
} else {
    Write-Host "==> No remotion-composer directory found — skipping npm install."
}

# 4) Install free offline TTS (optional)
Write-Host "==> Installing Piper TTS (optional)..."
& $PIP install piper-tts 2>$null || Write-Host "  [skip] piper-tts install failed — TTS will use cloud providers instead."

# 5) Warm npx HyperFrames cache (optional)
Write-Host "==> Warming HyperFrames npx cache (optional)..."
try {
    $env:PATH = "C:\Program Files\nodejs;" + $env:PATH
    npx --yes hyperframes --version | Out-Null
    Write-Host "    HyperFrames CLI cached."
} catch {
    Write-Host "  [skip] HyperFrames cache warm failed — offline or npm unavailable."
}

# 6) Copy .env if missing
$envExample = Join-Path $WORKTREE ".env.example"
$envFile    = Join-Path $WORKTREE ".env"
if ((Test-Path $envExample) -and -not (Test-Path $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host "==> Created .env from .env.example — add your API keys there."
} elseif (Test-Path $envFile) {
    Write-Host "==> .env already exists — skipping."
}

Write-Host ""
Write-Host "Setup complete for worktree: $WORKTREE"
