# Stops the hidden Streamlit server started by start.ps1.
#
# Deliberately narrow: only kills python processes whose command line mentions
# both Streamlit and this repo, so an unrelated Python or another Streamlit app
# on the machine is left alone.
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

$targets = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'streamlit' -and $_.CommandLine -match [regex]::Escape($leaf) }

if (-not $targets) {
    Notify 'The app is not running.' 'Information'
    exit 0
}

foreach ($process in $targets) {
    try { Stop-Process -Id $process.ProcessId -Force } catch {}
}

Notify "Stopped $($targets.Count) process(es)." 'Information'
