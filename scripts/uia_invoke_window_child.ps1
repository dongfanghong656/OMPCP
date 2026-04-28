param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [int]$ChildIndex = -1,
    [string]$NameOrClassPattern,
    [int]$Occurrence = 0,
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\uia_invoke_window_child.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class UiaInvokeWinByTitle {
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

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004

function Write-Log {
    param([string]$Message)
    $Message | Add-Content -Path $LogPath -Encoding UTF8
}

if (Test-Path $LogPath) {
    Remove-Item $LogPath -Force
}
Write-Log "BEGIN=$(Get-Date -Format o)"
Write-Log "TitlePattern=$TitlePattern"
Write-Log "ChildIndex=$ChildIndex"
Write-Log "NameOrClassPattern=$NameOrClassPattern"

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$target = [IntPtr]::Zero
$targetTitle = ''

[UiaInvokeWinByTitle]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [UiaInvokeWinByTitle]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [UiaInvokeWinByTitle]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [UiaInvokeWinByTitle]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

if ($target -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND"
    exit 1
}

[UiaInvokeWinByTitle]::ShowWindow($target, 9) | Out-Null
[UiaInvokeWinByTitle]::BringWindowToTop($target) | Out-Null
[UiaInvokeWinByTitle]::SetForegroundWindow($target) | Out-Null
Start-Sleep -Milliseconds 500

$root = [System.Windows.Automation.AutomationElement]::FromHandle($target)
$children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
Write-Log "TITLE=$targetTitle"
Write-Log "DESCENDANTS=$($children.Count)"

$candidate = $null
if ($ChildIndex -ge 0) {
    $candidate = $children.Item($ChildIndex)
} elseif (-not [string]::IsNullOrWhiteSpace($NameOrClassPattern)) {
    $filterRegex = [regex]::new($NameOrClassPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $matchIndex = 0
    for ($i = 0; $i -lt $children.Count; $i++) {
        try {
            $child = $children.Item($i)
            $current = $child.Current
            if ($filterRegex.IsMatch($current.Name) -or $filterRegex.IsMatch($current.ClassName)) {
                if ($matchIndex -eq $Occurrence) {
                    $candidate = $child
                    break
                }
                $matchIndex++
            }
        } catch {}
    }
}

if (-not $candidate) {
    Write-Log "NO_CANDIDATE"
    exit 1
}

$c = $candidate.Current
$rect = $c.BoundingRectangle
Write-Log ("CANDIDATE NAME={0} CLASS={1} TYPE={2} OFF={3} RECT={4:N0},{5:N0},{6:N0},{7:N0}" -f $c.Name, $c.ClassName, $c.ControlType.ProgrammaticName, $c.IsOffscreen, $rect.Left, $rect.Top, $rect.Right, $rect.Bottom)

$invoked = $false
try {
    $invokeObj = $null
    if ($candidate.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invokeObj)) {
        Write-Log "INVOKE_PATTERN=YES"
        $invokeObj.Invoke()
        $invoked = $true
    } else {
        Write-Log "INVOKE_PATTERN=NO"
    }
} catch {
    Write-Log "INVOKE_ERROR=$($_.Exception.Message)"
}

if (-not $invoked) {
    $x = [int](($rect.Left + $rect.Right) / 2)
    $y = [int](($rect.Top + $rect.Bottom) / 2)
    Write-Log "FALLBACK_CLICK=$x,$y"
    [UiaInvokeWinByTitle]::SetCursorPos($x, $y) | Out-Null
    Start-Sleep -Milliseconds 100
    [UiaInvokeWinByTitle]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [UiaInvokeWinByTitle]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}

Write-Log "END=$(Get-Date -Format o)"
Get-Content $LogPath -Raw
