param(
    [string]$TitlePattern = 'Autodesk Viewer',
    [string]$OutputCsv = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_selected_properties.csv',
    [string]$OutputMarkdown = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_selected_properties.md',
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\extract_autodesk_property_panel.log',
    [int]$PanelLeft = 2050,
    [int]$PanelTop = 470,
    [int]$PanelBottom = 1250
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class AutodeskPropertyExtractorWin32 {
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
    $script:propertyTarget = [IntPtr]::Zero
    $script:propertyTargetTitle = ''
    $regex = [regex]::new($Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    [AutodeskPropertyExtractorWin32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [AutodeskPropertyExtractorWin32]::IsWindowVisible($hWnd)) {
            return $true
        }
        $len = [AutodeskPropertyExtractorWin32]::GetWindowTextLength($hWnd)
        if ($len -le 0) {
            return $true
        }
        $sb = New-Object System.Text.StringBuilder ($len + 20)
        [AutodeskPropertyExtractorWin32]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $title = $sb.ToString()
        if ($regex.IsMatch($title)) {
            $script:propertyTarget = $hWnd
            $script:propertyTargetTitle = $title
            return $false
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return [pscustomobject]@{ Handle = $script:propertyTarget; Title = $script:propertyTargetTitle }
}

Remove-Item -LiteralPath $OutputCsv, $OutputMarkdown, $LogPath -ErrorAction SilentlyContinue
Write-Log "BEGIN=$(Get-Date -Format o)"

$targetInfo = Get-TargetWindow -Pattern $TitlePattern
if ($targetInfo.Handle -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND=$TitlePattern"
    exit 1
}
Write-Log "TARGET=$($targetInfo.Title)"

[AutodeskPropertyExtractorWin32]::ShowWindow($targetInfo.Handle, 9) | Out-Null
[AutodeskPropertyExtractorWin32]::BringWindowToTop($targetInfo.Handle) | Out-Null
[AutodeskPropertyExtractorWin32]::SetForegroundWindow($targetInfo.Handle) | Out-Null
Start-Sleep -Milliseconds 500

$root = [System.Windows.Automation.AutomationElement]::FromHandle($targetInfo.Handle)
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
        if ($rect.Left -lt $PanelLeft -or $rect.Top -lt $PanelTop -or $rect.Top -gt $PanelBottom) {
            continue
        }
        if ($current.IsOffscreen) {
            continue
        }
        $items.Add([pscustomobject]@{
            UiIndex = $i
            Text = $name
            Left = [int][math]::Round($rect.Left)
            Top = [int][math]::Round($rect.Top)
            Right = [int][math]::Round($rect.Right)
            Bottom = [int][math]::Round($rect.Bottom)
        })
    } catch {}
}

$groups = [System.Collections.Generic.List[object]]::new()
$sorted = @($items | Sort-Object Top, Left)
foreach ($item in $sorted) {
    $existing = $null
    foreach ($group in $groups) {
        if ([math]::Abs($group.Top - $item.Top) -le 12) {
            $existing = $group
            break
        }
    }
    if ($null -eq $existing) {
        $cellList = [System.Collections.Generic.List[object]]::new()
        $cellList.Add($item)
        $groups.Add([pscustomobject]@{
            Top = $item.Top
            Cells = $cellList
        })
    } else {
        $existing.Cells.Add($item)
    }
}

$rows = [System.Collections.Generic.List[object]]::new()
$rowIndex = 1
foreach ($group in ($groups | Sort-Object Top)) {
    $cells = @($group.Cells | Sort-Object Left)
    $label = if ($cells.Count -ge 1) { $cells[0].Text } else { '' }
    $value = if ($cells.Count -ge 2) { (($cells | Select-Object -Skip 1 | ForEach-Object { $_.Text }) -join ' | ') } else { '' }
    $rows.Add([pscustomobject]@{
        Row = $rowIndex
        Label = $label
        Value = $value
        Text = (($cells | ForEach-Object { $_.Text }) -join ' | ')
        Bounds = (($cells | ForEach-Object { "$($_.Left),$($_.Top),$($_.Right),$($_.Bottom)" }) -join '; ')
    })
    $rowIndex++
}

$rows | Export-Csv -Path $OutputCsv -Encoding UTF8 -NoTypeInformation

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# Autodesk Viewer Selected Properties')
$md.Add('')
$md.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$md.Add('')
$md.Add("Rows: $($rows.Count)")
$md.Add('')
$md.Add('| Row | Label | Value |')
$md.Add('| --- | --- | --- |')
foreach ($row in $rows) {
    $label = $row.Label.Replace('|', '\|')
    $value = $row.Value.Replace('|', '\|')
    $md.Add("| $($row.Row) | ``$label`` | ``$value`` |")
}
$md | Set-Content -Path $OutputMarkdown -Encoding UTF8

Write-Log "ROWS=$($rows.Count)"
Write-Log "CSV=$OutputCsv"
Write-Log "MARKDOWN=$OutputMarkdown"
Write-Log "END=$(Get-Date -Format o)"

Get-Content $LogPath -Raw
