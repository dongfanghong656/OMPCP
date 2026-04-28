param(
    [string]$OutputPath = "C:\codex-data\default_desktop_window_probe.txt",
    [string]$ProcessFilter = "eDrawings;EModelViewer;eDrawingOfficeAutomator;edRemoteWindow;powershell",
    [int]$MaxChildren = 80
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class DefaultDesktopWinProbe {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
}
'@

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$names = if ($ProcessFilter -eq '*' -or [string]::IsNullOrWhiteSpace($ProcessFilter)) {
    @()
} else {
    $ProcessFilter.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries -bor [System.StringSplitOptions]::TrimEntries)
}
$procs = if ($names.Count -gt 0) {
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName }
} else {
    Get-Process -ErrorAction SilentlyContinue
}

"PROCESSES" | Add-Content $OutputPath
($procs | Select-Object ProcessName, Id, SessionId, MainWindowHandle, MainWindowTitle, Responding | Format-Table -AutoSize | Out-String) | Add-Content $OutputPath

$pids = @($procs | Select-Object -ExpandProperty Id)
"ENUM_WINDOWS" | Add-Content $OutputPath
[DefaultDesktopWinProbe]::EnumWindows({
    param($hWnd, $lParam)
    $windowPid = 0
    [DefaultDesktopWinProbe]::GetWindowThreadProcessId($hWnd, [ref]$windowPid) | Out-Null
    if ($pids -contains [int]$windowPid) {
        $txtLen = [DefaultDesktopWinProbe]::GetWindowTextLength($hWnd)
        $sb = New-Object System.Text.StringBuilder ($txtLen + 50)
        [DefaultDesktopWinProbe]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $cb = New-Object System.Text.StringBuilder 256
        [DefaultDesktopWinProbe]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
        $procName = ''
        try { $procName = (Get-Process -Id $windowPid -ErrorAction Stop).ProcessName } catch { $procName = '<unknown>' }
        (" HWND=0x{0:X} PID={1} PNAME={2} VIS={3} CLASS={4} TITLE={5}" -f $hWnd.ToInt64(), $windowPid, $procName, [DefaultDesktopWinProbe]::IsWindowVisible($hWnd), $cb.ToString(), $sb.ToString()) | Add-Content $OutputPath
        try {
            $root = [System.Windows.Automation.AutomationElement]::FromHandle($hWnd)
            ("  UIA ROOT NAME={0} CLASS={1} ID={2} TYPE={3} OFF={4}" -f $root.Current.Name, $root.Current.ClassName, $root.Current.AutomationId, $root.Current.ControlType.ProgrammaticName, $root.Current.IsOffscreen) | Add-Content $OutputPath
            $children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
            ("  UIA DESCENDANTS={0}" -f $children.Count) | Add-Content $OutputPath
            for ($i = 0; $i -lt [Math]::Min($children.Count, $MaxChildren); $i++) {
                $child = $children.Item($i)
                ("   [{0}] NAME={1} CLASS={2} ID={3} TYPE={4} OFF={5}" -f $i, $child.Current.Name, $child.Current.ClassName, $child.Current.AutomationId, $child.Current.ControlType.ProgrammaticName, $child.Current.IsOffscreen) | Add-Content $OutputPath
            }
        } catch {
            ("  UIA ERROR={0}" -f $_.Exception.Message) | Add-Content $OutputPath
        }
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

Get-Content $OutputPath -Raw
