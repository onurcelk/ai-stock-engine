# Stops the hidden Streamlit server started by start.ps1.
#
# Deliberately narrow: only kills python processes whose command line mentions
# both Streamlit and this repo, so an unrelated Python or another Streamlit app
# on the machine is left alone.

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$leaf = Split-Path -Leaf $root

Add-Type -AssemblyName PresentationFramework

$targets = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'streamlit' -and $_.CommandLine -match [regex]::Escape($leaf) }

if (-not $targets) {
    [System.Windows.MessageBox]::Show('The app is not running.', 'Stock Prediction Models', 'OK', 'Information') | Out-Null
    exit 0
}

foreach ($process in $targets) {
    try { Stop-Process -Id $process.ProcessId -Force } catch {}
}

[System.Windows.MessageBox]::Show("Stopped $($targets.Count) process(es).", 'Stock Prediction Models', 'OK', 'Information') | Out-Null
