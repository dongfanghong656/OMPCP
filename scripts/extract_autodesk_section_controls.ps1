param(
    [string]$TitlePattern = 'Autodesk Viewer',
    [string]$OutputCsv = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_section_controls.csv',
    [string]$OutputMarkdown = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_section_controls.md',
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\extract_autodesk_section_controls.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class AutodeskSectionExtractorWin32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function Write-Log {
    param([string]$Message)
    $Message | Add-Content -Path $LogPath -Encoding UTF8
}

function Get-TargetWindow {
    param([string]$Pattern)
    $script:sectionTarget = [IntPtr]::Zero
    $script:sectionTargetTitle = ''
    $regex = [regex]::new($Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    [AutodeskSectionExtractorWin32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [AutodeskSectionExtractorWin32]::IsWindowVisible($hWnd)) {
            return $true
        }
        $len = [AutodeskSectionExtractorWin32]::GetWindowTextLength($hWnd)
        if ($len -le 0) {
            return $true
        }
        $sb = New-Object System.Text.StringBuilder ($len + 20)
        [AutodeskSectionExtractorWin32]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $title = $sb.ToString()
        if ($regex.IsMatch($title)) {
            $script:sectionTarget = $hWnd
            $script:sectionTargetTitle = $title
            return $false
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return [pscustomobject]@{ Handle = $script:sectionTarget; Title = $script:sectionTargetTitle }
}

Remove-Item -LiteralPath $OutputCsv, $OutputMarkdown, $LogPath -ErrorAction SilentlyContinue
Write-Log "BEGIN=$(Get-Date -Format o)"

$targetInfo = Get-TargetWindow -Pattern $TitlePattern
if ($targetInfo.Handle -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND=$TitlePattern"
    exit 1
}
Write-Log "TARGET=$($targetInfo.Title)"

[AutodeskSectionExtractorWin32]::ShowWindow($targetInfo.Handle, 9) | Out-Null
[AutodeskSectionExtractorWin32]::BringWindowToTop($targetInfo.Handle) | Out-Null
[AutodeskSectionExtractorWin32]::SetForegroundWindow($targetInfo.Handle) | Out-Null
Start-Sleep -Milliseconds 500

$root = [System.Windows.Automation.AutomationElement]::FromHandle($targetInfo.Handle)
$children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$rows = [System.Collections.Generic.List[object]]::new()

for ($i = 0; $i -lt $children.Count; $i++) {
    try {
        $child = $children.Item($i)
        $current = $child.Current
        $rect = $current.BoundingRectangle
        if ([double]::IsInfinity($rect.Left) -or [double]::IsInfinity($rect.Top) -or $current.IsOffscreen) {
            continue
        }
        if ($rect.Left -lt 900 -or $rect.Left -gt 1700 -or $rect.Top -lt 1235 -or $rect.Top -gt 1320) {
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
        $type = $current.ControlType.ProgrammaticName
        if ($type -ne 'ControlType.Button' -and $type -ne 'ControlType.Text') {
            continue
        }
        $rows.Add([pscustomobject]@{
            UiIndex = $i
            Name = $name
            Type = $type
            Selected = ($current.ClassName -match 'Mui-selected')
            ClassName = $current.ClassName
            Left = [int][math]::Round($rect.Left)
            Top = [int][math]::Round($rect.Top)
            Bounds = "$([int][math]::Round($rect.Left)),$([int][math]::Round($rect.Top)),$([int][math]::Round($rect.Right)),$([int][math]::Round($rect.Bottom))"
        })
    } catch {}
}

$sortedRows = @($rows | Sort-Object Top, Left, UiIndex)
$sortedRows | Export-Csv -Path $OutputCsv -Encoding UTF8 -NoTypeInformation

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# Autodesk Viewer Section Controls')
$md.Add('')
$md.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$md.Add('')
$md.Add("Rows: $($sortedRows.Count)")
$md.Add('')
$md.Add('| Name | Type | Selected | Bounds |')
$md.Add('| --- | --- | --- | --- |')
foreach ($row in $sortedRows) {
    $name = $row.Name.Replace('|', '\|')
    $md.Add("| ``$name`` | $($row.Type) | $($row.Selected) | $($row.Bounds) |")
}
$md | Set-Content -Path $OutputMarkdown -Encoding UTF8

Write-Log "ROWS=$($sortedRows.Count)"
Write-Log "CSV=$OutputCsv"
Write-Log "MARKDOWN=$OutputMarkdown"
Write-Log "END=$(Get-Date -Format o)"

Get-Content $LogPath -Raw
