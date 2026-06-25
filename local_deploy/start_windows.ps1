$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv_web\Scripts\python.exe"

if (!(Test-Path $Python)) {
    throw "Web virtual environment not found. Run local_deploy\install_windows.ps1 first."
}

& $Python (Join-Path $PSScriptRoot "run_server.py") --host 127.0.0.1 --port 7860
