param(
    [string]$FilePath,
    [string]$BatchCommand,
    [string]$MatlabRoot = 'C:\Program Files\MATLAB\R2024a',
[string]$WorkspaceRoot = 'C:\codex-data\OCT_Research_System'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Escape-MatlabLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ($Value -replace '\\', '/') -replace '''', ''''''
}

$matlabExe = Join-Path $MatlabRoot 'bin\matlab.exe'
if (-not (Test-Path $matlabExe)) {
    throw "MATLAB executable not found at $matlabExe"
}

$prefRoot = Join-Path $WorkspaceRoot '.matlab\prefdir_sessions'
New-Item -ItemType Directory -Force -Path $prefRoot | Out-Null
$prefDir = Join-Path $prefRoot ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $prefDir | Out-Null
$env:MATLAB_PREFDIR = $prefDir

$startupParts = @(
    'restoredefaultpath'
)

if ($BatchCommand) {
    $startupParts += $BatchCommand
} elseif ($FilePath) {
    if (-not (Test-Path $FilePath)) {
        throw "MATLAB file not found: $FilePath"
    }

    $resolvedFile = (Resolve-Path $FilePath).Path
    $fileDir = Split-Path -Parent $resolvedFile
    $startupParts += "cd('" + (Escape-MatlabLiteral -Value $fileDir) + "')"
    $startupParts += "run('" + (Escape-MatlabLiteral -Value $resolvedFile) + "')"
} else {
    throw 'Provide either -FilePath or -BatchCommand.'
}

$startupParts += 'exit'
$matlabBatch = $startupParts -join '; '

Write-Host "Using MATLAB root: $MatlabRoot"
Write-Host "Using workspace-local prefdir: $prefDir"
if ($FilePath) {
    Write-Host "Running MATLAB file: $FilePath"
}
if ($BatchCommand) {
    Write-Host "Running MATLAB batch command: $BatchCommand"
}

& $matlabExe -batch $matlabBatch
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "MATLAB exited with code $exitCode"
}
