param(
    [string]$TitlePattern = 'Autodesk Viewer',
    [string]$OutputCsv = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_measurements.csv',
    [string]$OutputMarkdown = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\autodesk_measurements.md',
    [string]$LogPath = 'C:\codex-data\OCT_Research_System\oct-research-assist\tmp\extract_autodesk_measurements.log'
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class AutodeskMeasurementExtractorWin32 {
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
    $script:measurementTarget = [IntPtr]::Zero
    $script:measurementTargetTitle = ''
    $regex = [regex]::new($Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    [AutodeskMeasurementExtractorWin32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [AutodeskMeasurementExtractorWin32]::IsWindowVisible($hWnd)) {
            return $true
        }
        $len = [AutodeskMeasurementExtractorWin32]::GetWindowTextLength($hWnd)
        if ($len -le 0) {
            return $true
        }
        $sb = New-Object System.Text.StringBuilder ($len + 20)
        [AutodeskMeasurementExtractorWin32]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
        $title = $sb.ToString()
        if ($regex.IsMatch($title)) {
            $script:measurementTarget = $hWnd
            $script:measurementTargetTitle = $title
            return $false
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return [pscustomobject]@{ Handle = $script:measurementTarget; Title = $script:measurementTargetTitle }
}

Remove-Item -LiteralPath $OutputCsv, $OutputMarkdown, $LogPath -ErrorAction SilentlyContinue
Write-Log "BEGIN=$(Get-Date -Format o)"

$targetInfo = Get-TargetWindow -Pattern $TitlePattern
if ($targetInfo.Handle -eq [IntPtr]::Zero) {
    Write-Log "NOT_FOUND=$TitlePattern"
    exit 1
}
Write-Log "TARGET=$($targetInfo.Title)"

[AutodeskMeasurementExtractorWin32]::ShowWindow($targetInfo.Handle, 9) | Out-Null
[AutodeskMeasurementExtractorWin32]::BringWindowToTop($targetInfo.Handle) | Out-Null
[AutodeskMeasurementExtractorWin32]::SetForegroundWindow($targetInfo.Handle) | Out-Null
Start-Sleep -Milliseconds 500

$root = [System.Windows.Automation.AutomationElement]::FromHandle($targetInfo.Handle)
$children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$items = [System.Collections.Generic.List[object]]::new()
$pattern = [regex]::new('^~?\s*[0-9]+(?:\.[0-9]+)?\s*(mm|cm|m|in)$', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)

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
        $text = $name.Trim()
        if (-not $pattern.IsMatch($text)) {
            continue
        }
        $rect = $current.BoundingRectangle
        if ([double]::IsInfinity($rect.Left) -or [double]::IsInfinity($rect.Top) -or $current.IsOffscreen) {
            continue
        }
        $valueMatch = [regex]::Match($text, '[0-9]+(?:\.[0-9]+)?')
        $unitMatch = [regex]::Match($text, '(mm|cm|m|in)$', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        $items.Add([pscustomobject]@{
            UiIndex = $i
            Text = $text
            NumericValue = if ($valueMatch.Success) { [double]$valueMatch.Value } else { $null }
            Unit = if ($unitMatch.Success) { $unitMatch.Value } else { '' }
            Left = [int][math]::Round($rect.Left)
            Top = [int][math]::Round($rect.Top)
            Right = [int][math]::Round($rect.Right)
            Bottom = [int][math]::Round($rect.Bottom)
        })
    } catch {}
}

$sorted = @($items | Sort-Object Top, Left)
$roles = @('Distance', 'X', 'Y', 'Z')
$rows = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $sorted.Count; $i++) {
    $role = if ($sorted.Count -eq 4 -and $i -lt $roles.Count) { $roles[$i] } else { "Measurement $($i + 1)" }
    $item = $sorted[$i]
    $rows.Add([pscustomobject]@{
        Role = $role
        Text = $item.Text
        NumericValue = $item.NumericValue
        Unit = $item.Unit
        Bounds = "$($item.Left),$($item.Top),$($item.Right),$($item.Bottom)"
        UiIndex = $item.UiIndex
    })
}

$rows | Export-Csv -Path $OutputCsv -Encoding UTF8 -NoTypeInformation

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# Autodesk Viewer Measurements')
$md.Add('')
$md.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$md.Add('')
$md.Add("Rows: $($rows.Count)")
$md.Add('')
$md.Add('| Role | Text | Numeric | Unit | Bounds |')
$md.Add('| --- | --- | --- | --- | --- |')
foreach ($row in $rows) {
    $md.Add("| $($row.Role) | ``$($row.Text)`` | $($row.NumericValue) | $($row.Unit) | $($row.Bounds) |")
}
$md | Set-Content -Path $OutputMarkdown -Encoding UTF8

Write-Log "ROWS=$($rows.Count)"
Write-Log "CSV=$OutputCsv"
Write-Log "MARKDOWN=$OutputMarkdown"
Write-Log "END=$(Get-Date -Format o)"

Get-Content $LogPath -Raw
