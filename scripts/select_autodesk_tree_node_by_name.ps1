param(
    [string]$TitlePattern = 'Autodesk Viewer',
    [Parameter(Mandatory = $true)]
    [string]$NodeName,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\select_autodesk_tree_node_by_name.log',
    [int]$Passes = 18,
    [int]$WheelDelta = -720,
    [switch]$DoubleClick,
    [switch]$Exact
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class AutodeskTreeSelectorWin32 {
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
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
'@

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004
$MOUSEEVENTF_WHEEL = 0x0800
$KEYEVENTF_KEYUP = 0x0002
$VK_ESCAPE = 0x1B

function Write-Log {
    param([string]$Message)
    $Message | Add-Content -Path $LogPath -Encoding UTF8
}

function Get-TargetWindow {
    param([string]$Pattern)
    $script:selectorTarget = [IntPtr]::Zero
    $script:selectorTargetTitle = ''
    $regex = [regex]::new($Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    [AutodeskTreeSelectorWin32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [AutodeskTreeSelectorWin32]::IsWindowVisible($hWnd)) {
            return $true
        }
        $len = [AutodeskTreeSelectorWin32]::GetWindowTextLength($hWnd)
        if ($len -le 0) {
            return $true
        }
        $sb = New-Object System.Text.StringBuilder ($len + 20)
        [AutodeskTreeSelectorWin32]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $title = $sb.ToString()
        if ($regex.IsMatch($title)) {
            $script:selectorTarget = $hWnd
            $script:selectorTargetTitle = $title
            return $false
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return [pscustomobject]@{ Handle = $script:selectorTarget; Title = $script:selectorTargetTitle }
}

function Invoke-Escape {
    [AutodeskTreeSelectorWin32]::keybd_event($VK_ESCAPE, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 50
    [AutodeskTreeSelectorWin32]::keybd_event($VK_ESCAPE, 0, $KEYEVENTF_KEYUP, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 150
}

function Invoke-Wheel {
    param([int]$Delta)
    [AutodeskTreeSelectorWin32]::SetCursorPos(220, 850) | Out-Null
    Start-Sleep -Milliseconds 70
    [AutodeskTreeSelectorWin32]::mouse_event($MOUSEEVENTF_WHEEL, 0, 0, $Delta, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 250
}

function Invoke-Click {
    param([int]$X, [int]$Y, [bool]$Twice)
    for ($n = 0; $n -lt ($(if ($Twice) { 2 } else { 1 })); $n++) {
        [AutodeskTreeSelectorWin32]::SetCursorPos($X, $Y) | Out-Null
        Start-Sleep -Milliseconds 80
        [AutodeskTreeSelectorWin32]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 80
        [AutodeskTreeSelectorWin32]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 120
    }
}

function Find-VisibleTextNode {
    param(
        [IntPtr]$Handle,
        [string]$TargetName,
        [bool]$ExactMatch
    )
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $matches = [System.Collections.Generic.List[object]]::new()
    for ($i = 0; $i -lt $children.Count; $i++) {
        try {
            $child = $children.Item($i)
            $current = $child.Current
            if ($current.ControlType.ProgrammaticName -ne 'ControlType.Text') {
                continue
            }
            $name = $current.Name
            if ($null -eq $name) {
                continue
            }
            $name = $name.Trim()
            if ([string]::IsNullOrWhiteSpace($name)) {
                continue
            }
            $rect = $current.BoundingRectangle
            if ([double]::IsInfinity($rect.Left) -or [double]::IsInfinity($rect.Top)) {
                continue
            }
            if ($rect.Left -lt 70 -or $rect.Left -gt 365 -or $rect.Top -lt 390 -or $rect.Top -gt 1210) {
                continue
            }
            $isMatch = if ($ExactMatch) {
                [string]::Equals($name, $TargetName, [System.StringComparison]::OrdinalIgnoreCase)
            } else {
                $name.IndexOf($TargetName, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
            if ($isMatch) {
                $matches.Add([pscustomobject]@{
                    UiIndex = $i
                    Name = $name
                    Left = [int][math]::Round($rect.Left)
                    Top = [int][math]::Round($rect.Top)
                    Right = [int][math]::Round($rect.Right)
                    Bottom = [int][math]::Round($rect.Bottom)
                })
            }
        } catch {}
    }
    return $matches
}

Remove-Item -LiteralPath $LogPath -ErrorAction SilentlyContinue
Write-Log "BEGIN=$(Get-Date -Format o)"
Write-Log "NodeName=$NodeName"
Write-Log "Exact=$($Exact.IsPresent)"
Write-Log "DoubleClick=$($DoubleClick.IsPresent)"

$targetInfo = Get-TargetWindow -Pattern $TitlePattern
if ($targetInfo.Handle -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND=$TitlePattern"
    exit 1
}
Write-Log "TARGET=$($targetInfo.Title)"

[AutodeskTreeSelectorWin32]::ShowWindow($targetInfo.Handle, 9) | Out-Null
[AutodeskTreeSelectorWin32]::BringWindowToTop($targetInfo.Handle) | Out-Null
[AutodeskTreeSelectorWin32]::SetForegroundWindow($targetInfo.Handle) | Out-Null
Start-Sleep -Milliseconds 500
Invoke-Escape

for ($i = 0; $i -lt 10; $i++) {
    Invoke-Wheel -Delta 900
}

for ($pass = 0; $pass -lt $Passes; $pass++) {
    $matches = @(Find-VisibleTextNode -Handle $targetInfo.Handle -TargetName $NodeName -ExactMatch $Exact.IsPresent)
    Write-Log "PASS=$pass MATCHES=$($matches.Count)"
    foreach ($match in $matches) {
        Write-Log "MATCH=$($match.Name) RECT=$($match.Left),$($match.Top),$($match.Right),$($match.Bottom) UI=$($match.UiIndex)"
    }
    if ($matches.Count -gt 0) {
        $selected = $matches |
            Sort-Object @{ Expression = { $_.Name.Length }; Ascending = $true }, Top |
            Select-Object -First 1
        $x = [int][math]::Round(($selected.Left + $selected.Right) / 2)
        $y = [int][math]::Round(($selected.Top + $selected.Bottom) / 2)
        Write-Log "CLICK=$x,$y NAME=$($selected.Name)"
        Invoke-Click -X $x -Y $y -Twice $DoubleClick.IsPresent
        Start-Sleep -Milliseconds 500
        Write-Log "END=$(Get-Date -Format o)"
        Get-Content $LogPath -Raw
        exit 0
    }
    Invoke-Wheel -Delta $WheelDelta
}

Write-Log "NO_MATCH"
Write-Log "END=$(Get-Date -Format o)"
Get-Content $LogPath -Raw
exit 2
