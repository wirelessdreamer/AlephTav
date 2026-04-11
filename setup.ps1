[CmdletBinding()]
param(
    [ValidateSet('full', 'fixture')]
    [string]$DataMode = 'full',
    [switch]$SkipInstall,
    [switch]$SkipRebuild,
    [switch]$SkipStart,
    [int]$ApiPort = 8000,
    [int]$UiPort = 5173,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $RootDir '.run'
$VenvDir = Join-Path $RootDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

$ApiProcess = $null
$UiProcess = $null
$ApiLog = $null
$UiLog = $null

function Write-Setup {
    param([string]$Message)
    Write-Host "[setup] $Message"
}

function Fail-Setup {
    param([string]$Message)
    throw "[setup] ERROR: $Message"
}

function Cleanup-Children {
    foreach ($process in @($UiProcess, $ApiProcess)) {
        if ($null -ne $process) {
            try {
                if (-not $process.HasExited) {
                    Stop-Process -Id $process.Id -Force
                }
            }
            catch {
            }
        }
    }
}

function Test-PythonVersion {
    param([string]$CommandName)

    try {
        & $CommandName -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Get-PythonCommand {
    foreach ($candidate in @('py', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            if ($candidate -eq 'py') {
                try {
                    & py -3.11 -c "import sys" *> $null
                    if ($LASTEXITCODE -eq 0) {
                        return 'py -3.11'
                    }
                }
                catch {
                }
            }
            elseif (Test-PythonVersion -CommandName $candidate) {
                return $candidate
            }
        }
    }
    return $null
}

function Invoke-PythonCommand {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    if ($PythonCommand -like 'py *') {
        & py -3.11 @Arguments
    }
    else {
        & $PythonCommand @Arguments
    }
}

function Get-PackageManager {
    foreach ($manager in @('winget', 'choco')) {
        if (Get-Command $manager -ErrorAction SilentlyContinue) {
            return $manager
        }
    }
    return $null
}

function Get-InstallCommands {
    param(
        [string]$PackageManager,
        [bool]$NeedPython,
        [bool]$NeedNode
    )

    $commands = [System.Collections.Generic.List[string]]::new()

    switch ($PackageManager) {
        'winget' {
            if ($NeedPython) {
                $commands.Add('winget install -e --id Python.Python.3.11')
            }
            if ($NeedNode) {
                $commands.Add('winget install -e --id OpenJS.NodeJS.LTS')
            }
        }
        'choco' {
            if ($NeedPython) {
                $commands.Add('choco install -y python311')
            }
            if ($NeedNode) {
                $commands.Add('choco install -y nodejs-lts')
            }
        }
    }

    return $commands
}

function Ensure-SystemRuntimes {
    $script:PythonCommand = Get-PythonCommand
    $needPython = $null -eq $script:PythonCommand
    $needNode = -not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)

    if (-not $needPython) {
        Write-Setup "Using Python runtime: $script:PythonCommand"
    }
    else {
        Write-Warning '[setup] Python 3.11+ was not found.'
    }

    if (-not $needNode) {
        Write-Setup "Using Node runtime: $(node --version) / npm $(npm --version)"
    }
    else {
        Write-Warning '[setup] Node.js and npm were not found.'
    }

    if (-not $needPython -and -not $needNode) {
        return
    }

    $manager = Get-PackageManager
    if ($null -eq $manager) {
        Fail-Setup 'No supported package manager was detected. Install Python 3.11+ and Node.js/npm manually, then re-run .\setup.ps1.'
    }

    $commands = Get-InstallCommands -PackageManager $manager -NeedPython:$needPython -NeedNode:$needNode
    Write-Setup "Missing required system runtimes."
    Write-Setup "Suggested install commands for $manager:"
    foreach ($command in $commands) {
        Write-Host $command
    }

    if ($Yes) {
        Write-Setup 'Auto-approving derived install commands because -Yes was supplied.'
    }
    else {
        $reply = Read-Host '[setup] Run these commands now? [y/N]'
        if ($reply -notmatch '^[Yy]$') {
            Fail-Setup 'Install the missing system runtimes, then re-run .\setup.ps1.'
        }
    }

    foreach ($command in $commands) {
        Write-Setup "Running: $command"
        Invoke-Expression $command
    }

    $script:PythonCommand = Get-PythonCommand
    if ($null -eq $script:PythonCommand) {
        Fail-Setup 'Python 3.11+ is still unavailable after the attempted installation.'
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Fail-Setup 'Node.js is still unavailable after the attempted installation.'
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Fail-Setup 'npm is still unavailable after the attempted installation.'
    }
}

function Invoke-Step {
    param(
        [string]$Description,
        [scriptblock]$Action
    )

    Write-Setup $Description
    & $Action
}

function Ensure-Venv {
    if (-not (Test-Path $VenvDir)) {
        Invoke-Step 'Creating virtual environment' {
            Invoke-PythonCommand -PythonCommand $script:PythonCommand -Arguments @('-m', 'venv', $VenvDir)
        }
    }
    else {
        Write-Setup "Using existing virtual environment at $VenvDir"
    }

    if (-not (Test-Path $VenvPython)) {
        Fail-Setup "Expected virtual environment interpreter at $VenvPython"
    }
}

function Install-ProjectDependencies {
    Invoke-Step 'Upgrading pip' {
        & $VenvPython -m pip install --upgrade pip
    }
    Invoke-Step 'Installing Python dependencies' {
        & $VenvPython -m pip install -e '.[dev]'
    }
    Invoke-Step 'Installing Node dependencies' {
        & npm install
    }
}

function Run-DataPipeline {
    if ($DataMode -eq 'fixture') {
        Invoke-Step 'Bootstrapping fixture data' {
            & $VenvPython 'scripts/bootstrap_fixture_repo.py'
        }
        return
    }

    Invoke-Step 'Seeding project metadata' {
        & $VenvPython 'scripts/seed_project.py'
    }
    Invoke-Step 'Importing Psalms data' {
        & $VenvPython 'scripts/import_psalms.py'
    }
    Invoke-Step 'Building indexes' {
        & $VenvPython 'scripts/build_indexes.py'
    }
    Invoke-Step 'Validating content' {
        & $VenvPython 'scripts/validate_content.py'
    }
}

function Test-PortFree {
    param([int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $Port)
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Wait-ForUrl {
    param(
        [string]$Url,
        [string]$Label,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -lt 500) {
                Write-Setup "$Label is ready at $Url"
                return
            }
        }
        catch {
        }
        Start-Sleep -Seconds 1
    }

    Fail-Setup "$Label failed to report ready startup in ${TimeoutSeconds}s."
}

function Start-Services {
    if (-not (Test-PortFree -Port $ApiPort)) {
        Fail-Setup "API port $ApiPort is already in use. Stop the conflicting process or pass -ApiPort."
    }
    if (-not (Test-PortFree -Port $UiPort)) {
        Fail-Setup "UI port $UiPort is already in use. Stop the conflicting process or pass -UiPort."
    }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:ApiLog = Join-Path $RunDir "setup-api-$timestamp.log"
    $script:UiLog = Join-Path $RunDir "setup-ui-$timestamp.log"

    Write-Setup "Starting API on http://127.0.0.1:$ApiPort"
    $script:ApiProcess = Start-Process -FilePath $VenvPython -ArgumentList @('-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") -WorkingDirectory $RootDir -RedirectStandardOutput $ApiLog -RedirectStandardError $ApiLog -PassThru
    Wait-ForUrl -Url "http://127.0.0.1:$ApiPort/health" -Label 'API'

    Write-Setup "Starting UI on http://127.0.0.1:$UiPort"
    $script:UiProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$UiPort") -WorkingDirectory $RootDir -RedirectStandardOutput $UiLog -RedirectStandardError $UiLog -PassThru
    Wait-ForUrl -Url "http://127.0.0.1:$UiPort" -Label 'UI'

    Write-Host ''
    Write-Setup 'Setup complete.'
    Write-Setup "API: http://127.0.0.1:$ApiPort"
    Write-Setup "UI:  http://127.0.0.1:$UiPort"
    Write-Setup "Logs:"
    Write-Setup "  API: $ApiLog"
    Write-Setup "  UI:  $UiLog"
    Write-Setup 'Press Ctrl+C to stop both services.'

    try {
        while ($true) {
            if ($ApiProcess.HasExited) {
                Fail-Setup "API exited unexpectedly. See $ApiLog"
            }
            if ($UiProcess.HasExited) {
                Fail-Setup "UI exited unexpectedly. See $UiLog"
            }
            Start-Sleep -Seconds 1
        }
    }
    finally {
        Cleanup-Children
    }
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

try {
    Ensure-SystemRuntimes
    Ensure-Venv

    if (-not $SkipInstall) {
        Install-ProjectDependencies
    }
    else {
        Write-Setup 'Skipping dependency installation.'
    }

    if (-not $SkipRebuild) {
        Run-DataPipeline
    }
    else {
        Write-Setup 'Skipping data bootstrap/rebuild.'
    }

    if (-not $SkipStart) {
        Start-Services
    }
    else {
        Write-Setup 'Verification and setup complete. Startup was skipped.'
    }
}
finally {
    Cleanup-Children
}
