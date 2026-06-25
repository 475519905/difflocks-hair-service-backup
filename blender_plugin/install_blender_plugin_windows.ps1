param(
    [string]$BlenderVersion = "5.1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Root "hair_generation_plugin"
$AddonRoot = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\scripts\addons"
$Target = Join-Path $AddonRoot "hair_generation_plugin"

New-Item -ItemType Directory -Force $AddonRoot | Out-Null
if (Test-Path $Target) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}
Copy-Item -LiteralPath $Source -Destination $Target -Recurse
Write-Host "Installed to: $Target"
Write-Host "Open Blender and enable the addon named Hair Generation Plugin / Chinese name in Blender UI."
