param(
    [string]$Label = 'edrawings-scenario',
    [string]$ArgumentList = '',
    [switch]$NoEnvIsolation,
    [switch]$WebViewOnly,
    [int]$WaitSeconds = 5
)

$ErrorActionPreference = 'Stop'

$base = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp'
$profileRoot = Join-Path $base ($Label + '-profile')
$windowsPath = Join-Path $base ($Label + '.windows.txt')

Get-Process eDrawings, EModelViewer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if (-not $NoEnvIsolation -and (Test-Path $profileRoot)) {
    Remove-Item -Recurse -Force $profileRoot -ErrorAction SilentlyContinue
}

$expArgs = @(
    '-NoProfile'
    '-ExecutionPolicy'
    'Bypass'
    '-File'
    'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\run_edrawings_experiment.ps1'
    '-Label'
    $Label
    '-ArgumentList'
    $ArgumentList
    '-ProfileRoot'
    $profileRoot
    '-WaitSeconds'
    $WaitSeconds
)
if ($NoEnvIsolation) {
    $expArgs += '-NoEnvIsolation'
}
if ($WebViewOnly) {
    $expArgs += '-WebViewOnly'
}

powershell @expArgs

powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\run_default_desktop_probe.ps1' `
    -OutputPath $windowsPath `
    -ProcessFilter '*' `
    -WaitSeconds 3
