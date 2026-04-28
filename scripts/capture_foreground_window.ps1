param(
    [string]$OutputImage = "C:\codex-data\foreground_window_capture.png",
    [string]$OutputText = "C:\codex-data\foreground_window_capture.txt",
    [int]$DelaySeconds = 5
)

if (Test-Path $OutputImage) {
    Remove-Item $OutputImage -Force
}
if (Test-Path $OutputText) {
    Remove-Item $OutputText -Force
}

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ForegroundWin {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, int nFlags);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
'@

Start-Sleep -Seconds $DelaySeconds

$hWnd = [ForegroundWin]::GetForegroundWindow()
if ($hWnd -eq [IntPtr]::Zero) {
    "NO_FOREGROUND_WINDOW" | Set-Content $OutputText
    exit 0
}

$txtLen = [ForegroundWin]::GetWindowTextLength($hWnd)
$sb = New-Object System.Text.StringBuilder ($txtLen + 20)
[ForegroundWin]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
$cb = New-Object System.Text.StringBuilder 256
[ForegroundWin]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
$windowPid = 0
[ForegroundWin]::GetWindowThreadProcessId($hWnd, [ref]$windowPid) | Out-Null

$rect = New-Object ForegroundWin+RECT
[ForegroundWin]::GetWindowRect($hWnd, [ref]$rect) | Out-Null
$width = [Math]::Max(1, $rect.Right - $rect.Left)
$height = [Math]::Max(1, $rect.Bottom - $rect.Top)

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$hdc = $graphics.GetHdc()
[ForegroundWin]::PrintWindow($hWnd, $hdc, 0) | Out-Null
$graphics.ReleaseHdc($hdc)
$graphics.Dispose()
$bitmap.Save($OutputImage, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()

@(
    "HANDLE=0x{0:X}" -f $hWnd.ToInt64()
    "PID=$windowPid"
    "TITLE=$($sb.ToString())"
    "CLASS=$($cb.ToString())"
    "RECT=$($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)"
    "IMAGE=$OutputImage"
) | Set-Content $OutputText
