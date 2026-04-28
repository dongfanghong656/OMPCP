param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$sourcePath = "C:\codex-data\OCT_Research_System\oct-research-assist\tools\desktop_gui_probe\DesktopDefaultLauncher.cs"
$outputPath = "C:\codex-data\OCT_Research_System\oct-research-assist\tools\desktop_gui_probe\DesktopDefaultLauncher.exe"
$compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path $compiler)) {
    throw "Compiler not found: $compiler"
}

$needsBuild = -not (Test-Path $outputPath) -or ((Get-Item $sourcePath).LastWriteTimeUtc -gt (Get-Item $outputPath).LastWriteTimeUtc)
if ($needsBuild) {
    & $compiler /nologo /t:exe /out:$outputPath $sourcePath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to compile DesktopDefaultLauncher.exe"
    }
}

& $outputPath @Command
