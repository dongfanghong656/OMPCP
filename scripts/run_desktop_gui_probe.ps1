param(
    [string]$TargetPath,
    [string]$OutputDirectory = "C:\codex-data\desktop-gui-probe-output",
    [int]$WaitMilliseconds = 8000,
    [string]$ProcessFilter = "eDrawings;EModelViewer;eDrawingOfficeAutomator;edRemoteWindow;explorer"
)

$project = "C:\codex-data\OCT_Research_System\oct-research-assist\tools\desktop_gui_probe\DesktopGuiProbe.csproj"

dotnet run --project $project -- `
    --target $TargetPath `
    --out-dir $OutputDirectory `
    --wait-ms $WaitMilliseconds `
    --process-filter $ProcessFilter
