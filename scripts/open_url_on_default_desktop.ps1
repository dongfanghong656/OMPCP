param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\open_url_on_default_desktop.log'
)

$ErrorActionPreference = 'Stop'

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("Timestamp=$(Get-Date -Format o)")
$lines.Add("Url=$Url")

try {
    Start-Process -FilePath $Url
    $lines.Add('StartResult=OK')
} catch {
    $lines.Add('StartResult=ERROR')
    $lines.Add("ExceptionType=$($_.Exception.GetType().FullName)")
    $lines.Add("ExceptionMessage=$($_.Exception.Message)")
}

$lines | Set-Content -Path $LogPath -Encoding UTF8
Get-Content $LogPath -Raw
