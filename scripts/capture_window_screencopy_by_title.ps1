param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [string]$OutputImage = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\window_screencopy.png',
    [string]$OutputText = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\window_screencopy.txt'
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ScreenCopyWinByTitle {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
'@

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$target = [IntPtr]::Zero
$targetTitle = ''
$targetClass = ''
$targetPid = 0

[ScreenCopyWinByTitle]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [ScreenCopyWinByTitle]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [ScreenCopyWinByTitle]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [ScreenCopyWinByTitle]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        $cb = New-Object System.Text.StringBuilder 256
        [ScreenCopyWinByTitle]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
        $script:targetClass = $cb.ToString()
        [uint32]$windowProcessId = 0
        [ScreenCopyWinByTitle]::GetWindowThreadProcessId($hWnd, [ref]$windowProcessId) | Out-Null
        $script:targetPid = $windowProcessId
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

if ($target -eq [IntPtr]::Zero) {
    "NOT_FOUND=$TitlePattern" | Set-Content -Path $OutputText -Encoding UTF8
    exit 0
}

[ScreenCopyWinByTitle]::ShowWindow($target, 9) | Out-Null
[ScreenCopyWinByTitle]::BringWindowToTop($target) | Out-Null
[ScreenCopyWinByTitle]::SetForegroundWindow($target) | Out-Null
Start-Sleep -Milliseconds 700

$rect = New-Object ScreenCopyWinByTitle+RECT
[ScreenCopyWinByTitle]::GetWindowRect($target, [ref]$rect) | Out-Null
$width = [Math]::Max(1, $rect.Right - $rect.Left)
$height = [Math]::Max(1, $rect.Bottom - $rect.Top)

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, [System.Drawing.Size]::new($width, $height))
$graphics.Dispose()
$bitmap.Save($OutputImage, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()

@(
    "HANDLE=0x{0:X}" -f $target.ToInt64()
    "PID=$targetPid"
    "TITLE=$targetTitle"
    "CLASS=$targetClass"
    "RECT=$($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)"
    "IMAGE=$OutputImage"
) | Set-Content -Path $OutputText -Encoding UTF8

Get-Content $OutputText -Raw
