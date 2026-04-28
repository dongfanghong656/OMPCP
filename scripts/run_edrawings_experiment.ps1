param(
    [string]$Label = 'edrawings-experiment',
    [string]$Target = 'C:\Program Files\Common Files\eDrawings2026\eDrawings.exe',
    [string]$ArgumentList = '',
    [string]$ProfileRoot = '',
    [int]$WaitSeconds = 8,
    [switch]$NoEnvIsolation,
    [switch]$WebViewOnly
)

$ErrorActionPreference = 'Stop'

$base = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp'
$logPath = Join-Path $base ($Label + '.log')
$procPath = Join-Path $base ($Label + '.processes.txt')

if (-not $ProfileRoot) {
    $ProfileRoot = Join-Path $base ($Label + '-profile')
}

Get-Process eDrawings, EModelViewer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

& 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\launch_edrawings_cleanenv.ps1' `
    -Target $Target `
    -ArgumentList $ArgumentList `
    -ProfileRoot $ProfileRoot `
    -WaitSeconds $WaitSeconds `
    -LogPath $logPath `
    -NoEnvIsolation:$NoEnvIsolation `
    -WebViewOnly:$WebViewOnly | Out-Null

Get-Process eDrawings, EModelViewer -ErrorAction SilentlyContinue |
    Select-Object Name, Id, MainWindowTitle, Responding, StartTime, Path |
    Format-List | Out-String | Set-Content -Path $procPath -Encoding UTF8

Get-Content $logPath
if (Test-Path $procPath) {
    ''
    '--- Processes ---'
    Get-Content $procPath
}
