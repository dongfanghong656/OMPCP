param(
    [string]$TitlePattern = 'Autodesk Viewer',
    [string]$OutputCsv = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_model_tree_nodes.csv',
    [string]$OutputMarkdown = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_model_tree_nodes.md',
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\collect_autodesk_model_tree.log',
    [int]$Passes = 22,
    [int]$WheelDelta = -720
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class AutodeskTreeCollectorWin32 {
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

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$MOUSEEVENTF_WHEEL = 0x0800

function Write-Log {
    param([string]$Message)
    $Message | Add-Content -Path $LogPath -Encoding UTF8
}

function Get-TargetWindow {
    param([string]$Pattern)
    $regex = [regex]::new($Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $script:collectorTarget = [IntPtr]::Zero
    $script:collectorTargetTitle = ''
    [AutodeskTreeCollectorWin32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [AutodeskTreeCollectorWin32]::IsWindowVisible($hWnd)) {
            return $true
        }
        $len = [AutodeskTreeCollectorWin32]::GetWindowTextLength($hWnd)
        if ($len -le 0) {
            return $true
        }
        $sb = New-Object System.Text.StringBuilder ($len + 20)
        [AutodeskTreeCollectorWin32]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $title = $sb.ToString()
        if ($regex.IsMatch($title)) {
            $script:collectorTarget = $hWnd
            $script:collectorTargetTitle = $title
            return $false
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return [pscustomobject]@{ Handle = $script:collectorTarget; Title = $script:collectorTargetTitle }
}

function Invoke-Wheel {
    param([int]$Delta)
    [AutodeskTreeCollectorWin32]::SetCursorPos(220, 850) | Out-Null
    Start-Sleep -Milliseconds 80
    [AutodeskTreeCollectorWin32]::mouse_event($MOUSEEVENTF_WHEEL, 0, 0, $Delta, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 250
}

function Get-VisibleTreeTextNodes {
    param(
        [IntPtr]$Handle,
        [int]$Pass
    )
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $items = [System.Collections.Generic.List[object]]::new()
    for ($i = 0; $i -lt $children.Count; $i++) {
        try {
            $child = $children.Item($i)
            $current = $child.Current
            if ($current.ControlType.ProgrammaticName -ne 'ControlType.Text') {
                continue
            }
            $name = $current.Name
            if ($null -eq $name) {
                $name = ''
            }
            $name = $name.Trim()
            if ([string]::IsNullOrWhiteSpace($name)) {
                continue
            }
            $rect = $current.BoundingRectangle
            if ([double]::IsInfinity($rect.Left) -or [double]::IsInfinity($rect.Top)) {
                continue
            }
            # Left panel model tree body in the current Autodesk Viewer layout.
            if ($rect.Left -lt 70 -or $rect.Left -gt 365) {
                continue
            }
            if ($rect.Top -lt 390 -or $rect.Top -gt 1210) {
                continue
            }
            if ($name -in @('模型', '搜索', 'Name')) {
                continue
            }
            $indent = [math]::Round(($rect.Left - 77) / 31)
            if ($indent -lt 0) {
                $indent = 0
            }
            $items.Add([pscustomobject]@{
                Pass = $Pass
                UiIndex = $i
                Name = $name
                Indent = [int]$indent
                Left = [int][math]::Round($rect.Left)
                Top = [int][math]::Round($rect.Top)
                Right = [int][math]::Round($rect.Right)
                Bottom = [int][math]::Round($rect.Bottom)
                Offscreen = $current.IsOffscreen
            })
        } catch {}
    }
    return $items
}

Remove-Item -LiteralPath $OutputCsv, $OutputMarkdown, $LogPath -ErrorAction SilentlyContinue
Write-Log "BEGIN=$(Get-Date -Format o)"

$targetInfo = Get-TargetWindow -Pattern $TitlePattern
if ($targetInfo.Handle -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND=$TitlePattern"
    exit 1
}

[AutodeskTreeCollectorWin32]::ShowWindow($targetInfo.Handle, 9) | Out-Null
[AutodeskTreeCollectorWin32]::BringWindowToTop($targetInfo.Handle) | Out-Null
[AutodeskTreeCollectorWin32]::SetForegroundWindow($targetInfo.Handle) | Out-Null
Start-Sleep -Milliseconds 500
Write-Log "TARGET=$($targetInfo.Title)"

# Move to top of model browser first.
for ($i = 0; $i -lt 10; $i++) {
    Invoke-Wheel -Delta 900
}

$all = [System.Collections.Generic.List[object]]::new()
for ($pass = 0; $pass -lt $Passes; $pass++) {
    $items = Get-VisibleTreeTextNodes -Handle $targetInfo.Handle -Pass $pass
    foreach ($item in $items) {
        $all.Add($item)
    }
    Write-Log "PASS=$pass ITEMS=$($items.Count)"
    Invoke-Wheel -Delta $WheelDelta
}

$dedup = $all |
    Group-Object Name |
    ForEach-Object {
        $_.Group |
            Sort-Object @{ Expression = 'Indent'; Ascending = $true }, @{ Expression = 'Pass'; Ascending = $true }, @{ Expression = 'Top'; Ascending = $true } |
            Select-Object -First 1
    } |
    Sort-Object Pass, Top, Name

$dedup | Export-Csv -Path $OutputCsv -Encoding UTF8 -NoTypeInformation

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# Autodesk Viewer Model Tree Summary')
$md.Add('')
$md.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$md.Add('')
$md.Add("Deduplicated nodes: $($dedup.Count)")
$md.Add('')
$md.Add('| Index | Level | Node | First pass | Bounds |')
$md.Add('| --- | --- | --- | --- | --- |')
$idx = 1
foreach ($item in $dedup) {
    $safeName = $item.Name.Replace('|', '\|')
    $md.Add("| $idx | $($item.Indent) | ``$safeName`` | $($item.Pass) | $($item.Left),$($item.Top),$($item.Right),$($item.Bottom) |")
    $idx++
}
$md | Set-Content -Path $OutputMarkdown -Encoding UTF8

Write-Log "CSV=$OutputCsv"
Write-Log "MARKDOWN=$OutputMarkdown"
Write-Log "DEDUP_COUNT=$($dedup.Count)"
Write-Log "END=$(Get-Date -Format o)"

Get-Content $LogPath -Raw
