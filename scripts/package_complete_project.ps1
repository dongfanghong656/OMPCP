param(
    [string]$SourceRoot = 'C:\codex-data\OCT_Research_System\oct-research-assist',
    [string]$ArchiveRoot = 'C:\codex-data\OCT_Research_System\project_archives'
)

$ErrorActionPreference = 'Stop'

$excludeDirs = @('__pycache__', '.pytest_cache', '_cache', 'tmp')

New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archivePath = Join-Path $ArchiveRoot ("oct_research_assist_complete_project_{0}.zip" -f $timestamp)
$manifestPath = Join-Path $ArchiveRoot ("oct_research_assist_complete_project_{0}.manifest.txt" -f $timestamp)

$items = Get-ChildItem -LiteralPath $SourceRoot -Force | Where-Object {
    $excludeDirs -notcontains $_.Name
}

Compress-Archive -Path ($items.FullName) -DestinationPath $archivePath -CompressionLevel Optimal -Force

$archiveInfo = Get-Item -LiteralPath $archivePath
$manifestLines = @(
    "Source: $SourceRoot"
    "Archive: $archivePath"
    "ArchiveSizeMB: $([math]::Round($archiveInfo.Length / 1MB, 2))"
    "Excluded top-level directories: $($excludeDirs -join ', ')"
    "Created: $(Get-Date -Format s)"
)

Set-Content -Path $manifestPath -Value $manifestLines -Encoding UTF8

Write-Output "ZIP=$archivePath"
Write-Output "MANIFEST=$manifestPath"
Write-Output "SIZE_MB=$([math]::Round($archiveInfo.Length / 1MB, 2))"
