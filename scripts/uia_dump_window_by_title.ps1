param(
    [Parameter(Mandatory = $true)]
    [string]$TitlePattern,
    [string]$OutputPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\uia_window_dump.txt',
    [int]$MaxChildren = 1000,
    [string]$NameOrClassPattern
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class UiaDumpWinByTitle {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$regex = [regex]::new($TitlePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$filterRegex = if ([string]::IsNullOrWhiteSpace($NameOrClassPattern)) {
    $null
} else {
    [regex]::new($NameOrClassPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

$target = [IntPtr]::Zero
$targetTitle = ''

[UiaDumpWinByTitle]::EnumWindows({
    param($hWnd, $lParam)
    if (-not [UiaDumpWinByTitle]::IsWindowVisible($hWnd)) {
        return $true
    }
    $len = [UiaDumpWinByTitle]::GetWindowTextLength($hWnd)
    if ($len -le 0) {
        return $true
    }
    $sb = New-Object System.Text.StringBuilder ($len + 20)
    [UiaDumpWinByTitle]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    $title = $sb.ToString()
    if ($regex.IsMatch($title)) {
        $script:target = $hWnd
        $script:targetTitle = $title
        return $false
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

if ($target -eq [IntPtr]::Zero) {
    "NOT_FOUND=$TitlePattern" | Set-Content -Path $OutputPath -Encoding UTF8
    exit 0
}

[UiaDumpWinByTitle]::ShowWindow($target, 9) | Out-Null
[UiaDumpWinByTitle]::BringWindowToTop($target) | Out-Null
[UiaDumpWinByTitle]::SetForegroundWindow($target) | Out-Null
Start-Sleep -Milliseconds 500

$root = [System.Windows.Automation.AutomationElement]::FromHandle($target)
$children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)

@(
    "TITLE=$targetTitle"
    ("HANDLE=0x{0:X}" -f $target.ToInt64())
    "DESCENDANTS=$($children.Count)"
) | Set-Content -Path $OutputPath -Encoding UTF8

for ($i = 0; $i -lt [Math]::Min($children.Count, $MaxChildren); $i++) {
    try {
        $child = $children.Item($i)
        $current = $child.Current
        $name = $current.Name
        $class = $current.ClassName
        if ($filterRegex -and -not ($filterRegex.IsMatch($name) -or $filterRegex.IsMatch($class))) {
            continue
        }
        $rect = $current.BoundingRectangle
        $patterns = @()
        foreach ($pattern in @(
            [System.Windows.Automation.InvokePattern]::Pattern,
            [System.Windows.Automation.ExpandCollapsePattern]::Pattern,
            [System.Windows.Automation.SelectionItemPattern]::Pattern,
            [System.Windows.Automation.ValuePattern]::Pattern,
            [System.Windows.Automation.ScrollItemPattern]::Pattern
        )) {
            try {
                $obj = $null
                if ($child.TryGetCurrentPattern($pattern, [ref]$obj)) {
                    $patterns += $pattern.ProgrammaticName
                }
            } catch {}
        }
        ("[{0}] NAME={1} CLASS={2} ID={3} TYPE={4} OFF={5} RECT={6:N0},{7:N0},{8:N0},{9:N0} PATTERNS={10}" -f `
            $i,
            $name,
            $class,
            $current.AutomationId,
            $current.ControlType.ProgrammaticName,
            $current.IsOffscreen,
            $rect.Left,
            $rect.Top,
            $rect.Right,
            $rect.Bottom,
            ($patterns -join ',')
        ) | Add-Content -Path $OutputPath -Encoding UTF8
    }
    catch {
        ("[{0}] ERROR={1}" -f $i, $_.Exception.Message) | Add-Content -Path $OutputPath -Encoding UTF8
    }
}

Get-Content $OutputPath -Raw
