param(
    [string]$TargetPath = "E:\三维模型\准直器.SLDASM",
    [string]$OutputPath = "C:\codex-data\interactive_edrawings_uia_probe.txt"
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinEnum3 {
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

Start-Process explorer.exe -ArgumentList $TargetPath
Start-Sleep -Seconds 8

$procs = Get-Process eDrawings, eDrawingOfficeAutomator, EModelViewer, edRemoteWindow -ErrorAction SilentlyContinue
"PROCESSES" | Add-Content $OutputPath
($procs | Select-Object ProcessName, Id, MainWindowHandle, MainWindowTitle, Responding | Format-Table -AutoSize | Out-String) | Add-Content $OutputPath

$pids = @($procs | Select-Object -ExpandProperty Id)
"ENUM_WINDOWS" | Add-Content $OutputPath
[WinEnum3]::EnumWindows({
    param($hWnd, $lParam)
    $windowPid = 0
    [WinEnum3]::GetWindowThreadProcessId($hWnd, [ref]$windowPid) | Out-Null
    if ($pids -contains [int]$windowPid) {
        $txtLen = [WinEnum3]::GetWindowTextLength($hWnd)
        $sb = New-Object System.Text.StringBuilder ($txtLen + 50)
        [WinEnum3]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $cb = New-Object System.Text.StringBuilder 256
        [WinEnum3]::GetClassName($hWnd, $cb, $cb.Capacity) | Out-Null
        (" HWND=0x{0:X} PID={1} VIS={2} CLASS={3} TITLE={4}" -f $hWnd.ToInt64(), $windowPid, [WinEnum3]::IsWindowVisible($hWnd), $cb.ToString(), $sb.ToString()) | Add-Content $OutputPath
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

$root = [System.Windows.Automation.AutomationElement]::RootElement
"UIA_CHILDREN" | Add-Content $OutputPath
foreach ($proc in $procs) {
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $proc.Id)
    $els = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
    (" PID={0} CHILDREN={1}" -f $proc.Id, $els.Count) | Add-Content $OutputPath
    for ($i = 0; $i -lt $els.Count; $i++) {
        $el = $els.Item($i)
        ("  TOP NAME={0} CLASS={1} ID={2} TYPE={3} OFF={4}" -f $el.Current.Name, $el.Current.ClassName, $el.Current.AutomationId, $el.Current.ControlType.ProgrammaticName, $el.Current.IsOffscreen) | Add-Content $OutputPath
        $kids = $el.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
        ("   KIDS={0}" -f $kids.Count) | Add-Content $OutputPath
        for ($j = 0; $j -lt [Math]::Min($kids.Count, 50); $j++) {
            $k = $kids.Item($j)
            ("   CHILD NAME={0} CLASS={1} ID={2} TYPE={3} OFF={4}" -f $k.Current.Name, $k.Current.ClassName, $k.Current.AutomationId, $k.Current.ControlType.ProgrammaticName, $k.Current.IsOffscreen) | Add-Content $OutputPath
        }
    }
}

Get-Content $OutputPath -Raw
