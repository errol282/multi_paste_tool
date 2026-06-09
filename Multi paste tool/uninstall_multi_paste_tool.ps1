$ErrorActionPreference = "Stop"

$appName = "Multi Paste"
$appDir = Join-Path $env:LOCALAPPDATA "Programs\$appName"
$startMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$appName.lnk"
$startupShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\$appName.lnk"

if (Test-Path $startMenuShortcut) {
    Remove-Item -LiteralPath $startMenuShortcut -Force
}

if (Test-Path $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}

Write-Host "Removed Start Menu and startup shortcuts for $appName."
Write-Host "Installed app folder:"
Write-Host $appDir
Write-Host "Delete that folder only if you also want to remove the local app files and saved data."
