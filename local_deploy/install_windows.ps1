param(
    [switch]$CloneDiffLocks,
    [switch]$InstallDiffLocksDeps,
    [switch]$Start,
    [string]$Python = "python",
    [string]$BlenderPath = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Venv = Join-Path $Root ".venv_web"
$DataDir = Join-Path $Root "runtime_data"
$ThirdParty = Join-Path $Root "third_party"
$DiffLocksDir = Join-Path $ThirdParty "difflocks"
$EnvPath = Join-Path $Root ".env"

New-Item -ItemType Directory -Force $DataDir, $ThirdParty | Out-Null

if (!(Test-Path $Venv)) {
    & $Python -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Root "server\requirements.txt")

if ($CloneDiffLocks -and !(Test-Path $DiffLocksDir)) {
    git clone https://github.com/Meshcapade/difflocks $DiffLocksDir
}

if ($InstallDiffLocksDeps -and (Test-Path $DiffLocksDir)) {
    $DiffReq = Join-Path $DiffLocksDir "requirements.txt"
    if (Test-Path $DiffReq) {
        & $VenvPython -m pip install -r $DiffReq
    }
}

if (!(Test-Path $EnvPath)) {
    $envLines = @(
        "DIFFLOCKS_PUBLIC=1",
        "DIFFLOCKS_WEB_PASSWORD=",
        "HAIRGEN_INVITE_CODE=",
        "DIFFLOCKS_WEB_DATA=$($DataDir -replace '\\','/')",
        "DIFFLOCKS_REPO=$($DiffLocksDir -replace '\\','/')",
        "DIFFLOCKS_PYTHON=$($VenvPython -replace '\\','/')",
        "BLENDER_PATH=$($BlenderPath -replace '\\','/')",
        "DIFFLOCKS_INPROCESS=1",
        "HAIRGEN_FACE_MODEL_PROVIDER=off",
        "HAIRGEN_FACE_MODEL_MODE=cpu"
    )
    Set-Content -LiteralPath $EnvPath -Value $envLines -Encoding UTF8
}

Write-Host "Local Web environment is ready."
Write-Host "Download DiffLocks checkpoints separately and place them under third_party/difflocks as required by the official project."
Write-Host "For CUDA inference, install NATTEN and FlashAttention-2 according to the official DiffLocks README."
Write-Host "Start command: powershell -ExecutionPolicy Bypass -File .\local_deploy\start_windows.ps1"

if ($Start) {
    & (Join-Path $PSScriptRoot "start_windows.ps1")
}
