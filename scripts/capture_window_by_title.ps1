param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [string]$OutputImage = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\window_capture.png',
    [string]$OutputText = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\window_capture.txt',
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

function Write-CaptureLog {
    param([string]$Message)
    if ($LogPath) {
        "[capture] $(Get-Date -Format o) $Message" | Add-Content -Path $LogPath -Encoding UTF8
    }
}

Write-CaptureLog "loading System.Drawing"
Add-Type -AssemblyName System.Drawing
Write-CaptureLog "loading Win32 declarations"
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class CaptureWinByTitle {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, int nFlags);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
'@

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$target = [IntPtr]::Zero
$targetTitle = ''
$targetClass = ''
$targetPid = 0

Write-CaptureLog "enumerating windows: $TitlePattern"
[CaptureWinByTitle]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [CaptureWinByTitle]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [CaptureWinByTitle]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [CaptureWinByTitle]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        Write-CaptureLog "matched hwnd=0x$($hWnd.ToInt64().ToString('X')) title=$title"
        $script:target = $hWnd
        $script:targetTitle = $title
        $cb = New-Object System.Text.StringBuilder 256
        [CaptureWinByTitle]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
        $script:targetClass = $cb.ToString()
        [uint32]$windowProcessId = 0
        [CaptureWinByTitle]::GetWindowThreadProcessId($hWnd, [ref]$windowProcessId) | Out-Null
        $script:targetPid = $windowProcessId
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null
Write-CaptureLog "enumeration complete"

if ($target -eq [IntPtr]::Zero) {
    Write-CaptureLog "no matching window"
    "NOT_FOUND=$TitlePattern" | Set-Content -Path $OutputText -Encoding UTF8
    exit 0
}

Write-CaptureLog "getting window rect"
$rect = New-Object CaptureWinByTitle+RECT
[CaptureWinByTitle]::GetWindowRect($target, [ref]$rect) | Out-Null
$width = [Math]::Max(1, $rect.Right - $rect.Left)
$height = [Math]::Max(1, $rect.Bottom - $rect.Top)
Write-CaptureLog "rect=$($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom) size=$width x $height"

Write-CaptureLog "creating bitmap"
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$hdc = $graphics.GetHdc()
Write-CaptureLog "calling PrintWindow"
[CaptureWinByTitle]::PrintWindow($target, $hdc, 0) | Out-Null
Write-CaptureLog "PrintWindow returned"
$graphics.ReleaseHdc($hdc)
$graphics.Dispose()
Write-CaptureLog "saving bitmap: $OutputImage"
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

Write-CaptureLog "wrote metadata: $OutputText"
Get-Content $OutputText -Raw
