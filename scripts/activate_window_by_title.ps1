param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\activate_window_by_title.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinActivateByTitle {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  public static readonly IntPtr HWND_TOP = IntPtr.Zero;
}
'@

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("Timestamp=$(Get-Date -Format o)")
$lines.Add("Pattern=$TitlePattern")

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$target = [IntPtr]::Zero
$targetTitle = ''

[WinActivateByTitle]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [WinActivateByTitle]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [WinActivateByTitle]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 10)
    [WinActivateByTitle]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

if ($target -eq [IntPtr]::Zero) {
    $lines.Add('MatchResult=NOT_FOUND')
} else {
    [WinActivateByTitle]::ShowWindow($target, 9) | Out-Null
    [WinActivateByTitle]::BringWindowToTop($target) | Out-Null
    [WinActivateByTitle]::SetForegroundWindow($target) | Out-Null
    $lines.Add('MatchResult=FOUND')
    $lines.Add(("Handle=0x{0:X}" -f $target.ToInt64()))
    $lines.Add("Title=$targetTitle")
}

$lines | Set-Content -Path $LogPath -Encoding UTF8
Get-Content $LogPath -Raw
