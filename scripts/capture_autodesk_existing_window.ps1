$ErrorActionPreference = 'Stop'

$base = 'C:\codex-data\OCT_Research_System\oct-research-assist'
$captureScript = Join-Path $base 'scripts\capture_window_by_title.ps1'
$outputImage = Join-Path $base 'tmp\autodesk_existing_window.png'
$outputText = Join-Path $base 'tmp\autodesk_existing_window.txt'
$logPath = Join-Path $base 'tmp\autodesk_existing_window.log'

try {
    @(
        "BEGIN=$(Get-Date -Format o)"
        "USER=$env:USERNAME"
        "PWD=$(Get-Location)"
        "SCRIPT=$captureScript"
    ) | Set-Content -Path $logPath -Encoding UTF8

    & $captureScript `
        -TitlePattern 'Autodesk Viewer' `
        -OutputImage $outputImage `
        -OutputText $outputText `
        -LogPath $logPath 2>&1 |
        Tee-Object -FilePath $logPath -Append

    "END=$(Get-Date -Format o)" | Add-Content -Path $logPath -Encoding UTF8
}
catch {
    "ERROR=$(Get-Date -Format o)" | Add-Content -Path $logPath -Encoding UTF8
    ($_ | Format-List * -Force | Out-String) | Add-Content -Path $logPath -Encoding UTF8
    if ($_.ScriptStackTrace) {
        $_.ScriptStackTrace | Add-Content -Path $logPath -Encoding UTF8
    }
    exit 1
}
