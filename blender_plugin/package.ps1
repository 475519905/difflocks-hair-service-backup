$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist = Join-Path $Root "dist"
$Source = Join-Path $Root "hair_generation_plugin"
$Zip = Join-Path $Dist "hair_generation_plugin.zip"

New-Item -ItemType Directory -Force $Dist | Out-Null
if (Test-Path $Zip) {
    Remove-Item -LiteralPath $Zip -Force
}
Compress-Archive -Path $Source -DestinationPath $Zip -Force
Write-Host "Plugin package created: $Zip"
