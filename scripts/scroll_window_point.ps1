param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [Parameter(Mandatory = $true)]
    [int]$X,
    [Parameter(Mandatory = $true)]
    [int]$Y,
    [int]$WheelDelta = -720,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\scroll_window_point.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ScrollWinPoint {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, UIntPtr dwExtraInfo);
}
'@

$MOUSEEVENTF_WHEEL = 0x0800

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

[ScrollWinPoint]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [ScrollWinPoint]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [ScrollWinPoint]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [ScrollWinPoint]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

Write-Log "BEGIN=$(Get-Date -Format o)"
Write-Log "TargetTitle=$targetTitle"
Write-Log "Point=$X,$Y"
Write-Log "WheelDelta=$WheelDelta"

if ($target -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND"
    exit 1
}

[ScrollWinPoint]::ShowWindow($target, 9) | Out-Null
[ScrollWinPoint]::BringWindowToTop($target) | Out-Null
[ScrollWinPoint]::SetForegroundWindow($target) | Out-Null
Start-Sleep -Milliseconds 300
[ScrollWinPoint]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 100
[ScrollWinPoint]::mouse_event($MOUSEEVENTF_WHEEL, 0, 0, $WheelDelta, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 100
Write-Log "END=$(Get-Date -Format o)"
Get-Content $LogPath -Raw
