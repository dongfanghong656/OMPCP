param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
$configAbs = (Resolve-Path $ConfigPath).Path
$config = Get-Content -Raw $configAbs | ConvertFrom-Json
$reportDir = $config.output_root
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportPath = Join-Path $reportDir "zotero-probe.md"

$lines = @()
$lines += "# Zotero Probe"
$lines += ""

$zoteroExe = "C:\Program Files\Zotero\zotero.exe"
if (Test-Path $zoteroExe) {
    $lines += "- Zotero executable: present"
    $lines += "- Path: $zoteroExe"
} else {
    $lines += "- Zotero executable: missing"
}
$lines += ""

$profilesIni = Join-Path $env:APPDATA "Zotero\Zotero\profiles.ini"
$profileDirs = @()
$customDataDir = $null
$defaultProfile = $null

if (Test-Path $profilesIni) {
    $lines += "## Profile metadata"
    $lines += ""
    $lines += "- profiles.ini: $profilesIni"
    $lines += ""

    $profilesRaw = Get-Content -Raw $profilesIni
    $current = @{}
    foreach ($line in ($profilesRaw -split "`r?`n")) {
        if ($line -match '^\[(.+)\]$') {
            if ($current.ContainsKey("Path")) {
                $isRelative = $true
                if ($current.ContainsKey("IsRelative")) {
                    $isRelative = ($current["IsRelative"] -eq "1")
                }
                $profilePath = $current["Path"]
                if ($isRelative) {
                    $profilePath = Join-Path (Split-Path $profilesIni -Parent) $profilePath
                }
                $resolvedProfilePath = [System.IO.Path]::GetFullPath($profilePath)
                $profileDirs += $resolvedProfilePath
                if ($current.ContainsKey("Default") -and $current["Default"] -eq "1") {
                    $defaultProfile = $resolvedProfilePath
                }
            }
            $current = @{}
            continue
        }
        if ($line -match '^([^=]+)=(.*)$') {
            $current[$matches[1]] = $matches[2]
        }
    }
    if ($current.ContainsKey("Path")) {
        $isRelative = $true
        if ($current.ContainsKey("IsRelative")) {
            $isRelative = ($current["IsRelative"] -eq "1")
        }
        $profilePath = $current["Path"]
        if ($isRelative) {
            $profilePath = Join-Path (Split-Path $profilesIni -Parent) $profilePath
        }
        $resolvedProfilePath = [System.IO.Path]::GetFullPath($profilePath)
        $profileDirs += $resolvedProfilePath
        if ($current.ContainsKey("Default") -and $current["Default"] -eq "1") {
            $defaultProfile = $resolvedProfilePath
        }
    }
}

if ($defaultProfile -and (Test-Path (Join-Path $defaultProfile "prefs.js"))) {
    $prefsPath = Join-Path $defaultProfile "prefs.js"
    $prefsRaw = Get-Content -Raw $prefsPath
    $lines += "- Default profile: $defaultProfile"
    if ($prefsRaw -match 'user_pref\("extensions\.zotero\.useDataDir",\s*true\);') {
        $lines += "- extensions.zotero.useDataDir: true"
    }
    if ($prefsRaw -match 'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]+)"\);') {
        $customDataDir = $matches[1] -replace '\\\\', '\'
        $lines += "- extensions.zotero.dataDir: $customDataDir"
    }
    $lines += ""
}

$candidateDirs = @()
$candidateDirs += $profileDirs
if ($customDataDir) {
    $candidateDirs += $customDataDir
}
$candidateDirs += @(
    (Join-Path $env:APPDATA "Zotero"),
    (Join-Path $env:USERPROFILE "Zotero"),
    (Join-Path $env:USERPROFILE "Documents\Zotero")
)
$candidateDirs = $candidateDirs | Where-Object { $_ } | Select-Object -Unique

$sqliteFiles = @()
foreach ($dir in $candidateDirs) {
    if (-not (Test-Path $dir)) {
        continue
    }
    $directSqlite = Join-Path $dir "zotero.sqlite"
    if (Test-Path $directSqlite) {
        $sqliteFiles += Get-Item $directSqlite
    }
    $sqliteFiles += Get-ChildItem -Path $dir -Recurse -File -Filter zotero.sqlite -ErrorAction SilentlyContinue
}
$sqliteFiles = $sqliteFiles | Sort-Object FullName -Unique

if ($sqliteFiles.Count -gt 0) {
    $lines += "## SQLite files"
    $lines += ""
    foreach ($file in $sqliteFiles) {
        $lines += "- $($file.FullName)"
    }
} else {
    $lines += "## SQLite files"
    $lines += ""
    $lines += "- None found in the standard profile locations."
}

$lines += ""
$lines += "## Next step"
$lines += ""
if ($sqliteFiles.Count -gt 0) {
    $lines += "- The vault can now use the located sqlite path for local Zotero indexing."
    $lines += "- If you later add a Zotero Web API key, keep SQLite as the fast local read path and use the API only for remote sync or writeback."
} else {
    $lines += "- If the main SQLite file is still missing, open Zotero once and let it finish initial setup before probing again."
}

Set-Content -Path $reportPath -Value ($lines -join "`n") -Encoding UTF8
Write-Output $reportPath
