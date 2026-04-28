param(
    [string]$Label = 'edrawings-shellopen',
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [int]$WaitSeconds = 8,
    [string]$ProfileRoot = '',
    [switch]$NoEnvIsolation,
    [switch]$WebViewOnly
)

$ErrorActionPreference = 'Stop'

$base = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp'
$logPath = Join-Path $base ($Label + '.log')
$windowsPath = Join-Path $base ($Label + '.windows.txt')
$procPath = Join-Path $base ($Label + '.processes.txt')

if (-not $ProfileRoot) {
    $ProfileRoot = Join-Path $base ($Label + '-profile')
}

if (-not $NoEnvIsolation) {
    $roaming = Join-Path $ProfileRoot 'Roaming'
    $local = Join-Path $ProfileRoot 'Local'
    $webview = Join-Path $roaming 'EDrawings\EBWebView'
    if (-not $WebViewOnly) {
        New-Item -ItemType Directory -Force -Path $roaming | Out-Null
        New-Item -ItemType Directory -Force -Path $local | Out-Null
        $env:APPDATA = $roaming
        $env:LOCALAPPDATA = $local
    }
    New-Item -ItemType Directory -Force -Path $webview | Out-Null
    $env:WEBVIEW2_USER_DATA_FOLDER = $webview
}

Get-Process eDrawings, EModelViewer -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("Timestamp=$(Get-Date -Format o)")
$lines.Add("LaunchMode=ShellOpen")
$lines.Add("FilePath=$FilePath")
$lines.Add("NoEnvIsolation=$NoEnvIsolation")
$lines.Add("WebViewOnly=$WebViewOnly")
$lines.Add("APPDATA=$($env:APPDATA)")
$lines.Add("LOCALAPPDATA=$($env:LOCALAPPDATA)")
$lines.Add("WEBVIEW2_USER_DATA_FOLDER=$($env:WEBVIEW2_USER_DATA_FOLDER)")

$launchedProc = Start-Process -FilePath $FilePath -PassThru
$lines.Add("LaunchedProcessName=$($launchedProc.ProcessName)")
$lines.Add("LaunchedProcessId=$($launchedProc.Id)")
Start-Sleep -Seconds $WaitSeconds

try {
    $launchedProc.Refresh()
    $lines.Add("LaunchedHasExited=$($launchedProc.HasExited)")
    if ($launchedProc.HasExited) {
        $lines.Add("LaunchedExitCode=$($launchedProc.ExitCode)")
        $lines.Add("LaunchedExitTime=$($launchedProc.ExitTime.ToString('o'))")
    } else {
        $lines.Add("LaunchedMainWindowHandle=$($launchedProc.MainWindowHandle)")
        $lines.Add("LaunchedResponding=$($launchedProc.Responding)")
    }
} catch {
    $lines.Add("LaunchedRefreshError=$($_.Exception.Message)")
}

$procs = Get-Process eDrawings, EModelViewer -ErrorAction SilentlyContinue
$lines.Add("ProcessCount=$(@($procs).Count)")
foreach ($proc in $procs) {
    $lines.Add("Process=$($proc.ProcessName) Id=$($proc.Id) MainWindowHandle=$($proc.MainWindowHandle) Responding=$($proc.Responding)")
}

$lines | Set-Content -Path $logPath -Encoding UTF8
$procs | Select-Object Name, Id, MainWindowHandle, MainWindowTitle, Responding, StartTime, Path | Format-List | Out-String | Set-Content -Path $procPath -Encoding UTF8

powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\codex-data\OCT_Research_System\oct-research-assist\scripts\run_default_desktop_probe.ps1' `
    -OutputPath $windowsPath `
    -ProcessFilter '*' `
    -WaitSeconds 3

Get-Content $logPath
''
'--- Processes ---'
Get-Content $procPath
