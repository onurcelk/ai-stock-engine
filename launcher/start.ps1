# Starts the desk -- the API and the Next.js frontend -- and opens a browser.
#
# Phase 7, the cutover. This used to start Streamlit directly; it now starts
# `run_desk.py`, which owns the startup prospective freeze, the missed-day
# replays and the ledger backup lifecycle. Pass -Streamlit for the fallback app
# (`run_app.py`), which is retained but is no longer the product.
#
# Safe to run twice: if the desk is already up it just opens a tab rather than
# starting a second server and failing on "port 3000 is already in use".
#
# -Quiet reports failures on stdout instead of in a dialog, and skips opening
# a browser. A dialog is right for a double-clicked shortcut but blocks
# forever when nobody is there to click it.

param([switch]$Quiet, [switch]$Streamlit)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($Streamlit) {
    $port = 8501
    $health = "http://localhost:$port/_stcore/health"
    $script = 'run_app.py'
    $marker = 'Scripts\streamlit.exe'
    # `run_app.py` forwards its arguments straight to Streamlit, so these have
    # to be Streamlit's own flags -- `--no-browser` is not one of them and
    # would be refused. The desk's launcher parses its own instead.
    $extra = @('--server.port', "$port", '--server.headless', 'true')
} else {
    $port = if ($env:DESK_WEB_PORT) { [int]$env:DESK_WEB_PORT } else { 3000 }
    $health = "http://localhost:$port/"
    $script = 'run_desk.py'
    # FastAPI, not uvicorn: .venv has uvicorn installed but not FastAPI, so a
    # check on the runner would pick the one virtualenv that cannot serve.
    $marker = 'Lib\site-packages\fastapi'
    $extra = @('--no-browser')
}
$url = "http://localhost:$port"

function Test-AppUp {
    try {
        $r = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Show-Problem($message) {
    if ($Quiet) { Write-Output $message; return }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, 'Stock Prediction Models', 'OK', 'Error') | Out-Null
}

function Open-App {
    if (-not $Quiet) { Start-Process $url }
}

if (Test-AppUp) {
    Open-App
    exit 0
}

# The repo has two virtualenvs; take the first that actually has what this
# mode needs -- uvicorn for the desk, Streamlit for the fallback.
$python = $null
$venv = $null
foreach ($name in @('.venv', 'venv')) {
    $candidate = Join-Path $root "$name\Scripts\python.exe"
    $required = Join-Path $root "$name\$marker"
    if ((Test-Path $candidate) -and (Test-Path $required)) {
        $python = $candidate
        $venv = $name
        break
    }
}

if (-not $python) {
    Show-Problem "No virtualenv with $marker found in`n$root`n`nExpected .venv\ or venv\ with it installed."
    exit 1
}

# Working directory must be the repo root: `api.main:app` is imported by module
# path, and the frontend is resolved relative to the repository.
$arguments = @($script) + $extra
Start-Process -FilePath $python -ArgumentList $arguments `
    -WorkingDirectory $root -WindowStyle Hidden

# Cold start loads TensorFlow through `core`, runs the prospective freeze over
# the collection universe, and then boots two servers, so allow a long wait.
for ($i = 0; $i -lt 480; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-AppUp) {
        Open-App
        exit 0
    }
}

Show-Problem "The desk did not come up on $url within 4 minutes.`n`nRun this to see why:`n  cd `"$root`"`n  .\$venv\Scripts\python.exe $script"
exit 1
