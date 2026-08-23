# Stops the hidden desk started by start.ps1, then backs the ledger up.
#
# Phase 7, the cutover. The desk is three processes -- the `run_desk.py`
# launcher, the uvicorn server it starts, and the Node server behind the
# frontend -- so this kills trees rather than processes. The Streamlit fallback
# is matched too, since either may be what is running.
#
# Deliberately narrow: only Python processes whose command line mentions this
# repository are touched, so an unrelated Python, another Streamlit app, or
# somebody else's Node server on this machine is left alone.
#
# **Why the backup is taken here.** A killed process does not run its shutdown
# hooks, so neither `run_desk.py`'s `finally` nor the API's lifespan gets to
# snapshot the forecast ledger. `ledger_lifecycle.shutdown` is fingerprint-
# guarded and never raises, so calling it once here -- after everything is
# down, with nothing left that could still be writing -- is exact rather than
# merely safe. Without it the snapshot would wait for the recovery pass on the
# next start, which is the path meant for a crash, not for the stop button.
#
# -Quiet suppresses the confirmation dialog. The dialog is the right thing when
# a shortcut is double-clicked, but it blocks forever when nobody is there to
# click it, which makes the script unusable from a script or a test.

param([switch]$Quiet)

$ErrorActionPreference = 'Stop'

function Notify($message, $icon) {
    if ($Quiet) { Write-Output $message; return }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, 'Stock Prediction Models', 'OK', $icon) | Out-Null
}

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$leaf = Split-Path -Leaf $root
$pattern = 'run_desk\.py|run_app\.py|uvicorn|streamlit'

$targets = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern -and $_.CommandLine -match [regex]::Escape($leaf) }

if (-not $targets) {
    Notify 'The desk is not running.' 'Information'
    exit 0
}

# /T takes the children with it: uvicorn under the launcher, and the Node
# server under that. Killing the launcher alone would leave the frontend
# holding port 3000, and the next start would fail on a port that looks free.
foreach ($process in $targets) {
    try { & taskkill /PID $process.ProcessId /T /F 2>&1 | Out-Null } catch {}
}

# The ledger snapshot the killed processes never got to take. Best effort by
# design -- `backup_if_changed` reports rather than raises -- so a missing
# backup drive stops the desk cleanly instead of failing the stop button.
$python = $null
foreach ($name in @('.venv', 'venv')) {
    $candidate = Join-Path $root "$name\Scripts\python.exe"
    if (Test-Path $candidate) { $python = $candidate; break }
}

$backup = ''
if ($python) {
    # `app/` reaches Python through PYTHONPATH rather than through a literal
    # inside -c. The repository path contains a space, and the quotes that
    # would need to survive PowerShell's native-argument parsing do not --
    # the interpreter received a bare `r C:\Users\...` and refused it.
    $env:PYTHONPATH = Join-Path $root 'app'
    try {
        $backup = "`n" + (& $python -c 'from core import ledger_lifecycle; print(ledger_lifecycle.shutdown().summary())' | Out-String).Trim()
    } catch {
        $backup = "`nLedger backup could not be taken; the next start will recover it."
    }
}

Notify "Stopped $($targets.Count) process(es).$backup" 'Information'
