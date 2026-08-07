# Starts the Streamlit app and opens it in the default browser.
#
# Safe to run twice: if the app is already up it just opens a tab rather than
# starting a second server and failing on "port 8501 is already in use".

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$port = 8501
$url = "http://localhost:$port"

function Test-AppUp {
    try {
        $r = Invoke-WebRequest -Uri "$url/_stcore/health" -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Show-Problem($message) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, 'Stock Prediction Models', 'OK', 'Error') | Out-Null
}

if (Test-AppUp) {
    Start-Process $url
    exit 0
}

# The repo has two virtualenvs; take the first that actually has Streamlit.
$python = $null
foreach ($name in @('.venv', 'venv')) {
    $candidate = Join-Path $root "$name\Scripts\python.exe"
    $marker = Join-Path $root "$name\Scripts\streamlit.exe"
    if ((Test-Path $candidate) -and (Test-Path $marker)) { $python = $candidate; break }
}

if (-not $python) {
    Show-Problem "No virtualenv with Streamlit found in`n$root`n`nExpected .venv\ or venv\ with Streamlit installed."
    exit 1
}

# Working directory must be the repo root: the app is launched by relative path
# and .streamlit\config.toml (the dark theme) is only read from there.
Start-Process -FilePath $python `
    -ArgumentList '-m', 'streamlit', 'run', 'app/streamlit_app.py',
                  '--server.port', $port, '--server.headless', 'true' `
    -WorkingDirectory $root -WindowStyle Hidden

# Cold start loads TensorFlow, so allow a generous wait before giving up.
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-AppUp) {
        Start-Process $url
        exit 0
    }
}

Show-Problem "The app did not come up on $url within 60 seconds.`n`nRun this to see why:`n  cd `"$root`"`n  .\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py"
exit 1
