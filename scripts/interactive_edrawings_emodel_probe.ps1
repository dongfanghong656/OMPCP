param(
    [string]$TargetPath = "E:\三维模型\准直器.SLDASM",
    [string]$OutputPath = "C:\codex-data\interactive_edrawings_emodel_probe.txt"
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$exe = "C:\Program Files\Common Files\eDrawings2026\EModelViewer.exe"
Start-Process -FilePath $exe -ArgumentList ('"' + $TargetPath + '"')
Start-Sleep -Seconds 10

$procs = Get-Process eDrawings, eDrawingOfficeAutomator, EModelViewer, edRemoteWindow -ErrorAction SilentlyContinue
($procs | Select-Object ProcessName, Id, MainWindowHandle, MainWindowTitle, Responding | Format-Table -AutoSize | Out-String) | Add-Content $OutputPath

Get-Content $OutputPath -Raw
