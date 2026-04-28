param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [Parameter(Mandatory = $true)]
    [int]$X,
    [Parameter(Mandatory = $true)]
    [int]$Y,
    [switch]$DoubleClick,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\click_window_point.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ClickWinPoint {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
'@

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004

if (Test-Path $LogPath) {
    Remove-Item $LogPath -Force
}

function Write-Log {
    param([string]$Message)
    $Message | Add-Content -Path $LogPath -Encoding UTF8
}

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$target = [IntPtr]::Zero
$targetTitle = ''

[ClickWinPoint]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [ClickWinPoint]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [ClickWinPoint]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [ClickWinPoint]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

Write-Log "BEGIN=$(Get-Date -Format o)"
Write-Log "TitlePattern=$TitlePattern"
Write-Log "TargetTitle=$targetTitle"
Write-Log "Point=$X,$Y"
Write-Log "DoubleClick=$($DoubleClick.IsPresent)"

if ($target -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND"
    exit 1
}

[ClickWinPoint]::ShowWindow($target, 9) | Out-Null
[ClickWinPoint]::BringWindowToTop($target) | Out-Null
[ClickWinPoint]::SetForegroundWindow($target) | Out-Null
Start-Sleep -Milliseconds 300

function Send-LeftClick {
    [ClickWinPoint]::SetCursorPos($X, $Y) | Out-Null
    Start-Sleep -Milliseconds 80
    [ClickWinPoint]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [ClickWinPoint]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}

Send-LeftClick
if ($DoubleClick) {
    Start-Sleep -Milliseconds 120
    Send-LeftClick
}

Write-Log "END=$(Get-Date -Format o)"
Get-Content $LogPath -Raw
