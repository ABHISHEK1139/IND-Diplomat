param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$envTemplatePath = Join-Path $projectRoot ".env.example"
$envPath = Join-Path $projectRoot ".env"

function Resolve-FirstExistingPath {
    param(
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Upsert-EnvValue {
    param(
        [string]$FilePath,
        [string]$Name,
        [string]$Value
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        New-Item -Path $FilePath -ItemType File -Force | Out-Null
    }

    $lines = @()
    if ((Get-Item -LiteralPath $FilePath).Length -gt 0) {
        $lines = Get-Content -LiteralPath $FilePath
    }

    $pattern = "^\s*" + [regex]::Escape($Name) + "="
    $updated = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = "$Name=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $lines += "$Name=$Value"
    }

    Set-Content -LiteralPath $FilePath -Value $lines -Encoding UTF8
}

Write-Host "[first-run] Project root: $projectRoot"

if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $envTemplatePath)) {
        throw "Missing .env.example at $envTemplatePath"
    }

    Copy-Item -LiteralPath $envTemplatePath -Destination $envPath
    Write-Host "[first-run] Created .env from .env.example"
}

$globalRiskCandidates = @(
    (Join-Path $projectRoot "data\global_risk"),
    (Join-Path $projectRoot "data\global_risk_data"),
    (Join-Path $projectRoot "global_risk_data"),
    (Join-Path $projectRoot "SAVED DATA\global_risk_data")
)
$globalRiskDir = Resolve-FirstExistingPath -Candidates $globalRiskCandidates
if (-not $globalRiskDir) {
    $globalRiskDir = (Join-Path $projectRoot "data\global_risk")
}

$legalMemoryCandidates = @(
    (Join-Path $projectRoot "data\legal_memory"),
    (Join-Path $projectRoot "legal_memory"),
    (Join-Path $projectRoot "SAVED DATA\legal_memory")
)
$legalMemoryDir = Resolve-FirstExistingPath -Candidates $legalMemoryCandidates
if (-not $legalMemoryDir) {
    $legalMemoryDir = (Join-Path $projectRoot "data\legal_memory")
}

$globalRiskDirEnv = ($globalRiskDir -replace "\\", "/")
$legalMemoryDirEnv = ($legalMemoryDir -replace "\\", "/")

Upsert-EnvValue -FilePath $envPath -Name "GLOBAL_RISK_DIR" -Value $globalRiskDirEnv
Upsert-EnvValue -FilePath $envPath -Name "LEGAL_MEMORY_DIR" -Value $legalMemoryDirEnv

Write-Host "[first-run] GLOBAL_RISK_DIR=$globalRiskDirEnv"
Write-Host "[first-run] LEGAL_MEMORY_DIR=$legalMemoryDirEnv"

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if ($InstallDependencies) {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "[first-run] Creating virtual environment (.venv)"
        python -m venv "$projectRoot\.venv"
    }

    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Unable to locate .venv Python at $venvPython"
    }

    Write-Host "[first-run] Installing dependencies"
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")
}

Write-Host "[first-run] Setup complete."
Write-Host "[first-run] Next:"
Write-Host "  1) .\.venv\Scripts\Activate.ps1"
Write-Host "  2) python project_root.py"
Write-Host "  3) python app_server.py --port 8000"
