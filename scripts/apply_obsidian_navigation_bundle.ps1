param(
    [Parameter(Mandatory = $true)]
    [string]$BundleRoot,

    [Parameter(Mandatory = $true)]
    [string]$VaultRoot,

    [string]$BackupRoot
)

$bundle = (Resolve-Path -LiteralPath $BundleRoot).Path
$vault = (Resolve-Path -LiteralPath $VaultRoot).Path

if (-not $BackupRoot) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupRoot = Join-Path $bundle "..\\backup-$stamp"
}

$backup = [System.IO.Path]::GetFullPath($BackupRoot)
$files = Get-ChildItem -LiteralPath $bundle -Recurse -File

if (-not $files) {
    throw "Bundle root has no files: $bundle"
}

Write-Host "Bundle:" $bundle
Write-Host "Vault :" $vault
Write-Host "Backup:" $backup

$copied = 0
$backedUp = 0
foreach ($file in $files) {
    $relative = $file.FullName.Substring($bundle.Length).TrimStart('\')
    $target = Join-Path $vault $relative
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    if (Test-Path -LiteralPath $target) {
        $backupTarget = Join-Path $backup $relative
        $backupDir = Split-Path -Parent $backupTarget
        New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
        Copy-Item -LiteralPath $target -Destination $backupTarget -Force
        $backedUp++
    }

    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    $copied++
}

Write-Host "Copied files :" $copied
Write-Host "Backed up    :" $backedUp
