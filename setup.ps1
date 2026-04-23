[CmdletBinding()]
param(
    [ValidateSet('full', 'fixture')]
    [string]$DataMode = 'full',
    [switch]$SkipInstall,
    [switch]$SkipRebuild,
    [switch]$SkipStart,
    [int]$ApiPort = 8765,
    [int]$UiPort = 5173,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $RootDir '.run'
$VenvDir = Join-Path $RootDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$RebuildStateScript = Join-Path $RootDir 'scripts\setup_rebuild_state.py'
$ManagedServicesFile = Join-Path $RunDir 'managed-services.json'

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

function Clear-ManagedServicesState {
    if (Test-Path $ManagedServicesFile) {
        Remove-Item -Path $ManagedServicesFile -Force -ErrorAction SilentlyContinue
    }
}

function Write-ManagedServicesState {
    $payload = @{
        api = @{ pid = if ($null -ne $ApiProcess) { $ApiProcess.Id } else { $null }; port = $ApiPort }
        ui  = @{ pid = if ($null -ne $UiProcess) { $UiProcess.Id } else { $null }; port = $UiPort }
    }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $ManagedServicesFile -Encoding UTF8
}

function Stop-ManagedProcess {
    param(
        [int]$Pid,
        [string]$Label
    )

    if (-not $Pid) {
        return
    }

    $process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return
    }

    Stop-Process -Id $Pid -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 5; $i++) {
        Start-Sleep -Seconds 1
        $process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            return
        }
    }

    Write-Warning "[setup] $Label process $Pid did not exit cleanly; forcing shutdown."
    Stop-Process -Id $Pid -Force -ErrorAction SilentlyContinue
}

function Get-ListenerProcessId {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($null -eq $connection) {
        return $null
    }
    return [int]$connection.OwningProcess
}

function Test-RepoOwnedListener {
    param(
        [int]$Pid,
        [ValidateSet('api', 'ui')]
        [string]$Kind
    )

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $Pid" -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }

    $commandLine = $process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }

    switch ($Kind) {
        'api' {
            return $commandLine -like '*uvicorn*' -and $commandLine -like '*app.api.main:app*'
        }
        'ui' {
            return $commandLine -like '*vite*' -and $commandLine -like '*app/ui/vite.config.ts*' -and $commandLine -like "*$RootDir*"
        }
    }

    return $false
}

function Reclaim-RepoOwnedPort {
    param(
        [int]$Port,
        [ValidateSet('api', 'ui')]
        [string]$Kind
    )

    $pid = Get-ListenerProcessId -Port $Port
    if ($null -eq $pid) {
        return
    }

    if (Test-RepoOwnedListener -Pid $pid -Kind $Kind) {
        Write-Setup "Stopping existing repo-owned $($Kind.ToUpperInvariant()) process $pid on port $Port."
        Stop-ManagedProcess -Pid $pid -Label $Kind.ToUpperInvariant()
    }
}

function Cleanup-StaleManagedServices {
    if (-not (Test-Path $ManagedServicesFile)) {
        return
    }

    try {
        $payload = Get-Content -Path $ManagedServicesFile -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "[setup] Unable to parse $ManagedServicesFile; clearing stale setup state."
        Clear-ManagedServicesState
        return
    }

    foreach ($label in @('api', 'ui')) {
        $entry = $payload.$label
        if ($null -ne $entry -and $entry.pid) {
            $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
            if ($null -ne $process) {
                Write-Setup "Stopping stale setup-managed $($label.ToUpperInvariant()) process $($entry.pid) on port $($entry.port)."
                Stop-ManagedProcess -Pid ([int]$entry.pid) -Label $label.ToUpperInvariant()
            }
        }
    }

    Clear-ManagedServicesState
}

function Cleanup-Children {
    foreach ($process in @($UiProcess, $ApiProcess)) {
        if ($null -ne $process) {
            try {
                if (-not $process.HasExited) {
                    Stop-ManagedProcess -Pid $process.Id -Label 'setup child'
                }
            }
            catch {
            }
        }
    }
    Clear-ManagedServicesState
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

function Invoke-RebuildState {
    param(
        [ValidateSet('check', 'mark')]
        [string]$Action,
        [string]$Mode
    )

    $output = & $VenvPython $RebuildStateScript $Action '--mode' $Mode 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output | Out-String).Trim()
    }
}

function Invoke-TrackedDataPipeline {
    $status = Invoke-RebuildState -Action check -Mode $DataMode
    if ($status.Output) {
        Write-Setup $status.Output
    }

    if ($status.ExitCode -eq 0) {
        $mark = Invoke-RebuildState -Action mark -Mode $DataMode
        if ($mark.ExitCode -ne 0) {
            $message = if ($mark.Output) { $mark.Output } else { 'Unable to record rebuild state.' }
            Fail-Setup $message
        }
        if ($mark.Output) {
            Write-Setup $mark.Output
        }
        Write-Setup 'Skipping data bootstrap/rebuild because tracked outputs are current.'
        return
    }

    Run-DataPipeline
    $mark = Invoke-RebuildState -Action mark -Mode $DataMode
    if ($mark.ExitCode -ne 0) {
        $message = if ($mark.Output) { $mark.Output } else { 'Unable to record rebuild state.' }
        Fail-Setup $message
    }
    if ($mark.Output) {
        Write-Setup $mark.Output
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

function Get-AvailablePort {
    param(
        [int]$StartingPort,
        [string]$Label
    )

    if (Test-PortFree -Port $StartingPort) {
        return $StartingPort
    }

    for ($candidate = $StartingPort + 1; $candidate -le $StartingPort + 25; $candidate++) {
        if (Test-PortFree -Port $candidate) {
            Write-Warning "[setup] $Label port $StartingPort is already in use by another process. Falling back to $candidate."
            return $candidate
        }
    }

    Fail-Setup "$Label port $StartingPort is already in use and no fallback port was available in the next 25 ports. Pass an override flag."
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
    Reclaim-RepoOwnedPort -Port $ApiPort -Kind api
    Reclaim-RepoOwnedPort -Port $UiPort -Kind ui

    $script:ApiPort = Get-AvailablePort -StartingPort $ApiPort -Label 'API'
    $script:UiPort = Get-AvailablePort -StartingPort $UiPort -Label 'UI'

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
    Write-ManagedServicesState
    Wait-ForUrl -Url "http://127.0.0.1:$ApiPort/health" -Label 'API'

    Write-Setup "Starting UI on http://127.0.0.1:$UiPort"
    $script:UiProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$UiPort") -WorkingDirectory $RootDir -RedirectStandardOutput $UiLog -RedirectStandardError $UiLog -PassThru
    Write-ManagedServicesState
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
Cleanup-StaleManagedServices

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
        Invoke-TrackedDataPipeline
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
