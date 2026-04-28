$OutputPath = "C:\codex-data\edrawings_window_poll_20260423.txt"
$TargetPath = "E:\三维模型\准直器.SLDASM"

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinEnum2 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
}
'@

Start-Process explorer.exe -ArgumentList $TargetPath

for ($iter = 0; $iter -lt 20; $iter++) {
    $procs = Get-Process eDrawings, eDrawingOfficeAutomator, EModelViewer, edRemoteWindow -ErrorAction SilentlyContinue
    Add-Content $OutputPath ("ITER=" + $iter)
    ($procs | Select-Object ProcessName, Id, MainWindowHandle, MainWindowTitle, Responding | Format-Table -AutoSize | Out-String) | Add-Content $OutputPath

    $pids = @($procs | Select-Object -ExpandProperty Id)
    [WinEnum2]::EnumWindows({
        param($hWnd, $lParam)
        $pid2 = 0
        [WinEnum2]::GetWindowThreadProcessId($hWnd, [ref]$pid2) | Out-Null
        if ($pids -contains [int]$pid2) {
            $txtLen = [WinEnum2]::GetWindowTextLength($hWnd)
            $sb = New-Object System.Text.StringBuilder ($txtLen + 50)
            [WinEnum2]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
            $cb = New-Object System.Text.StringBuilder 256
            [WinEnum2]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
            Add-Content $OutputPath (" HWND=0x{0:X} PID={1} VIS={2} CLASS={3} TITLE={4}" -f $hWnd.ToInt64(), $pid2, [WinEnum2]::IsWindowVisible($hWnd), $cb.ToString(), $sb.ToString())
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null

    Start-Sleep -Milliseconds 800
}

Get-Content $OutputPath -Raw
