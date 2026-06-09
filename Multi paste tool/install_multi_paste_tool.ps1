param(
    [switch]$RunAtLogin
)

$ErrorActionPreference = "Stop"

$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appName = "Multi Paste"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs"
$appDir = Join-Path $installRoot $appName
$scriptPath = Join-Path $appDir "multi_paste_tool.py"
$iconPath = Join-Path $appDir "multi_paste_tool.ico"
$requirementsPath = Join-Path $appDir "requirements.txt"
$venvDir = Join-Path $appDir ".venv"
$pythonPath = Join-Path $venvDir "Scripts\python.exe"
$pythonwPath = Join-Path $venvDir "Scripts\pythonw.exe"
$logPath = Join-Path $appDir "install.log"

function Write-Step {
    param([string]$Message)
    Write-Host $Message
    Add-Content -Path $logPath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
}

function Invoke-LoggedCommand {
    param(
        [string]$FilePath,
        [string]$ArgumentList,
        [string]$FailureMessage
    )

    $stdoutPath = Join-Path $env:TEMP "multi-paste-install-stdout.txt"
    $stderrPath = Join-Path $env:TEMP "multi-paste-install-stderr.txt"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    if (Test-Path $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath | Tee-Object -FilePath $logPath -Append
    }
    if (Test-Path $stderrPath) {
        Get-Content -LiteralPath $stderrPath | Tee-Object -FilePath $logPath -Append
    }

    $exitCode = $process.ExitCode
    if ($exitCode -ne 0) {
        throw "$FailureMessage Exit code: $exitCode"
    }
}

New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Set-Content -Path $logPath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Installing $appName"

$payloadFiles = @(
    "multi_paste_tool.py",
    "requirements.txt",
    "multi_paste_tool.ico",
    "README.md",
    "run_multi_paste_tool.bat",
    "install_multi_paste_tool.ps1",
    "install_multi_paste_tool.bat",
    "install_multi_paste_tool_startup.bat",
    "uninstall_multi_paste_tool.ps1",
    "uninstall_multi_paste_tool.bat"
)

Write-Step "Installing app files to $appDir..."
foreach ($fileName in $payloadFiles) {
    $sourcePath = Join-Path $sourceDir $fileName
    $targetPath = Join-Path $appDir $fileName
    if (Test-Path $sourcePath) {
        if ((Resolve-Path $sourcePath).Path -ne (Resolve-Path -LiteralPath $targetPath -ErrorAction SilentlyContinue).Path) {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        }
    }
}

if (-not (Test-Path $scriptPath)) {
    throw "Could not find installed app file at $scriptPath"
}

if (-not (Test-Path $venvDir)) {
    Write-Step "Creating local Python environment..."
    Invoke-LoggedCommand -FilePath "py" -ArgumentList "-m venv `"$venvDir`"" -FailureMessage "Could not create virtual environment."
}

if (-not (Test-Path $pythonPath)) {
    throw "Could not find venv Python at $pythonPath"
}

Write-Step "Installing Python dependencies..."
Invoke-LoggedCommand -FilePath $pythonPath -ArgumentList "-m pip install -r `"$requirementsPath`"" -FailureMessage "Could not install Python dependencies."

if (-not (Test-Path $pythonwPath)) {
    throw "Could not find windowless Python at $pythonwPath"
}

$shell = New-Object -ComObject WScript.Shell
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenuDir "$appName.lnk"

Write-Step "Creating Start Menu shortcut..."
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$scriptPath`""
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = "Multi Paste clipboard hotkey tool"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()

if ($RunAtLogin) {
    $startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
    $startupShortcutPath = Join-Path $startupDir "$appName.lnk"
    Write-Step "Creating Windows startup shortcut..."
    $startupShortcut = $shell.CreateShortcut($startupShortcutPath)
    $startupShortcut.TargetPath = $pythonwPath
    $startupShortcut.Arguments = "`"$scriptPath`""
    $startupShortcut.WorkingDirectory = $appDir
    $startupShortcut.Description = "Multi Paste clipboard hotkey tool"
    if (Test-Path $iconPath) {
        $startupShortcut.IconLocation = "$iconPath,0"
    }
    $startupShortcut.Save()
}

Write-Step "Installed. Use Start Menu -> Multi Paste."
Write-Host ""
Write-Host "Installed $appName."
Write-Host "Install folder: $appDir"
Write-Host "Start Menu shortcut: $shortcutPath"
Write-Host "Normal launch uses pythonw.exe, so no command prompt window opens."
