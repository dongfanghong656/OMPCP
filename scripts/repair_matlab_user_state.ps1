param(
    [switch]$ResetRoamingPrefs,
    [switch]$WhatIfOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$localRoot = Join-Path $env:LOCALAPPDATA 'MathWorks\MATLAB\R2024a'
$roamingRoot = Join-Path $env:APPDATA 'MathWorks\MATLAB\R2024a'

function Backup-ItemIfPresent {
    param(
        [Parameter(Mandatory = $true)][string]$PathToBackup
    )

    if (-not (Test-Path $PathToBackup)) {
        Write-Host "Skip missing path: $PathToBackup"
        return
    }

    $backupPath = "$PathToBackup.codex-bak-$timestamp"
    if ($WhatIfOnly) {
        Write-Host "[WhatIf] Move $PathToBackup -> $backupPath"
        return
    }

    Move-Item -Path $PathToBackup -Destination $backupPath
    Write-Host "Backed up: $PathToBackup -> $backupPath"
}

Write-Host '=== MATLAB user-state repair ==='
Write-Host "Local MATLAB state root: $localRoot"
Write-Host "Roaming MATLAB state root: $roamingRoot"

if (Test-Path $localRoot) {
    try {
        $cacheFiles = @(Get-ChildItem -Path $localRoot -Filter 'toolbox_cache-*.xml' -ErrorAction Stop)
        if ($cacheFiles.Count -eq 0) {
            Write-Host 'No toolbox cache files found under local MATLAB state.'
        } else {
            foreach ($cacheFile in $cacheFiles) {
                Backup-ItemIfPresent -PathToBackup $cacheFile.FullName
            }
        }
    } catch {
        Write-Host 'Could not enumerate local MATLAB cache files from the current shell.'
        Write-Host 'If you run this script directly in your own PowerShell session, it should still be able to back up toolbox_cache-*.xml.'
    }
} else {
    Write-Host 'Local MATLAB state root does not exist.'
}

if ($ResetRoamingPrefs) {
    Backup-ItemIfPresent -PathToBackup $roamingRoot
} else {
    Write-Host 'Roaming MATLAB preferences were left untouched. Re-run with -ResetRoamingPrefs only if startup still fails after clearing cache.'
}

Write-Host ''
Write-Host 'Next steps:'
Write-Host '1. Close all MATLAB and VS Code windows.'
Write-Host '2. Re-run MATLAB once or use the workspace fallback task.'
Write-Host '3. If direct startup still fails, re-run this script with -ResetRoamingPrefs.'
