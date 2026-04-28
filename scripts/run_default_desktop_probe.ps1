param(
    [string]$OutputPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\default-desktop-probe.txt',
    [string]$ProcessFilter = 'eDrawings;EModelViewer',
    [int]$WaitSeconds = 3,
    [int]$MaxChildren = 80
)

$ErrorActionPreference = 'Stop'

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

& 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\invoke_on_default_desktop.ps1' `
    powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\default_desktop_window_probe.ps1' `
    -OutputPath $OutputPath `
    -ProcessFilter $ProcessFilter `
    -MaxChildren $MaxChildren | Out-Null

Start-Sleep -Seconds $WaitSeconds

if (Test-Path $OutputPath) {
    Get-Content $OutputPath -Raw
} else {
    "NOFILE=$OutputPath"
}
