param(
    [string]$Target = 'C:\Program Files\Common Files\eDrawings2026\eDrawings.exe',
    [string]$ArgumentList = '',
    [string]$ProfileRoot = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\edrawings-clean-env',
    [string]$LogPath = '',
    [int]$WaitSeconds = 10,
    [switch]$WebViewOnly,
    [switch]$NoEnvIsolation
)

$ErrorActionPreference = 'Stop'

$roaming = Join-Path $ProfileRoot 'Roaming'
$local = Join-Path $ProfileRoot 'Local'
$webview = Join-Path $roaming 'EDrawings\EBWebView'
$logTarget = if ($LogPath) { $LogPath } else { Join-Path $ProfileRoot 'launch.log' }

if (-not $NoEnvIsolation) {
    New-Item -ItemType Directory -Force -Path $webview | Out-Null
}

if ((-not $NoEnvIsolation) -and (-not $WebViewOnly)) {
    New-Item -ItemType Directory -Force -Path $roaming | Out-Null
    New-Item -ItemType Directory -Force -Path $local | Out-Null
    $env:APPDATA = $roaming
    $env:LOCALAPPDATA = $local
}

if (-not $NoEnvIsolation) {
    $env:WEBVIEW2_USER_DATA_FOLDER = $webview
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Target
$psi.Arguments = $ArgumentList
$psi.WorkingDirectory = Split-Path -Path $Target -Parent
$psi.UseShellExecute = $true

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("Timestamp=$(Get-Date -Format o)")
$lines.Add("Target=$Target")
$lines.Add("Arguments=$ArgumentList")
$lines.Add("NoEnvIsolation=$NoEnvIsolation")
$lines.Add("WebViewOnly=$WebViewOnly")
$lines.Add("WaitSeconds=$WaitSeconds")
$lines.Add("APPDATA=$($env:APPDATA)")
$lines.Add("LOCALAPPDATA=$($env:LOCALAPPDATA)")
$lines.Add("WEBVIEW2_USER_DATA_FOLDER=$($env:WEBVIEW2_USER_DATA_FOLDER)")

try {
    $proc = [System.Diagnostics.Process]::Start($psi)
    if ($null -ne $proc) {
        $lines.Add("StartResult=OK")
        $lines.Add("StartedProcessId=$($proc.Id)")
        if ($WaitSeconds -gt 0) {
            Start-Sleep -Seconds $WaitSeconds
            $proc.Refresh()
            $lines.Add("ObservedAfterWait=True")
            $lines.Add("HasExited=$($proc.HasExited)")
            if ($proc.HasExited) {
                $lines.Add("ExitCode=$($proc.ExitCode)")
                $lines.Add("ExitTime=$($proc.ExitTime.ToString('o'))")
            } else {
                $lines.Add("MainWindowHandle=$($proc.MainWindowHandle)")
                $lines.Add("Responding=$($proc.Responding)")
            }
        }
    } else {
        $lines.Add("StartResult=NULL")
    }
} catch {
    $lines.Add("StartResult=ERROR")
    $lines.Add("ExceptionType=$($_.Exception.GetType().FullName)")
    $lines.Add("ExceptionMessage=$($_.Exception.Message)")
}

$lines | Set-Content -Path $logTarget -Encoding UTF8
$lines
