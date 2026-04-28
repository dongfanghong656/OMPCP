param(
    [string]$Label = 'edrawings-regreset-test',
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string]$BackupPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\eDrawings-e2026-backup-20260423.reg',
    [int]$WaitSeconds = 10
)

$ErrorActionPreference = 'Stop'
$keyPath = 'Registry::HKEY_CURRENT_USER\Software\eDrawings\e2026'

if (-not (Test-Path $BackupPath)) {
    reg export HKCU\Software\eDrawings\e2026 $BackupPath /y | Out-Null
}

if (Test-Path $keyPath) {
    Remove-Item $keyPath -Recurse -Force
}

powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\invoke_on_default_desktop.ps1' `
    powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\run_file_association_probe_scenario.ps1' `
    -Label $Label `
    -FilePath $FilePath `
    -WaitSeconds $WaitSeconds | Out-Null

Start-Sleep -Seconds ($WaitSeconds + 4)

Get-Content ("C:\codex-data\OCT_Research_System\oct-research-assist\tmp\" + $Label + '.log')
