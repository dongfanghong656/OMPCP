param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [string]$Label = 'chrome-url-probe',
    [int]$WaitSeconds = 12
)

$ErrorActionPreference = 'Stop'

$base = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp'
$windowsPath = Join-Path $base ($Label + '.windows.txt')
$foregroundImage = Join-Path $base ($Label + '.foreground.png')
$foregroundText = Join-Path $base ($Label + '.foreground.txt')

Start-Process -FilePath $Url
Start-Sleep -Seconds $WaitSeconds

powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\run_default_desktop_probe.ps1' `
    -OutputPath $windowsPath `
    -ProcessFilter 'chrome' `
    -WaitSeconds 2 | Out-Null

powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\invoke_on_default_desktop.ps1' `
    powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\capture_foreground_window.ps1' `
    -OutputImage $foregroundImage `
    -OutputText $foregroundText `
    -DelaySeconds 1 | Out-Null

Get-Content $windowsPath -Raw
