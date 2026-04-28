param(
    [string]$SourcePath = "C:\codex-data\OMPCP",
    [string]$Owner = "dongfanghong656",
    [string]$Repo = "OMPCP",
    [string]$Branch = "main",
    [string]$CommitMessage = "Initialize OMPCP OCT Mie PSF diagnostic stack",
    [string]$TokenEnvName = "GITHUB_TOKEN",
    [switch]$AllowReplaceRemoteTree,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-GitHubToken {
    param([string]$Name)
    $token = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not $token) {
        $token = [Environment]::GetEnvironmentVariable("GH_TOKEN", "Process")
    }
    if (-not $token) {
        throw "Missing GitHub token. Set `$env:$Name or `$env:GH_TOKEN in this PowerShell session. Do not write tokens into files."
    }
    return $token
}

function New-GitHubHeaders {
    param([string]$Token)
    return @{
        "Authorization" = "Bearer $Token"
        "Accept" = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent" = "OMPCP-Codex-Publisher"
    }
}

function Invoke-GitHubJson {
    param(
        [ValidateSet("GET", "POST", "PATCH", "PUT")]
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers,
        $Body = $null,
        [switch]$AllowNotFound
    )
    try {
        if ($null -eq $Body) {
            return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers -TimeoutSec 120
        }
        $json = $Body | ConvertTo-Json -Depth 20 -Compress
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers -Body $json -ContentType "application/json" -TimeoutSec 120
    }
    catch {
        $response = $_.Exception.Response
        if ($AllowNotFound -and $response -and ([int]$response.StatusCode -eq 404 -or [int]$response.StatusCode -eq 409)) {
            return $null
        }
        $detail = $_.Exception.Message
        try {
            if ($response) {
                $stream = $response.GetResponseStream()
                if ($stream) {
                    $reader = [System.IO.StreamReader]::new($stream)
                    $detail = $reader.ReadToEnd()
                    $reader.Dispose()
                }
            }
        }
        catch {
            # Preserve the original exception detail.
        }
        throw "GitHub API request failed: $Method $Uri`n$detail"
    }
}

function Test-ExcludedRelativePath {
    param([string]$RelativePath)
    $normalized = $RelativePath -replace "\\", "/"
    if ($normalized -like ".git/*") { return $true }
    if ($normalized -like "__pycache__/*" -or $normalized -like "*/__pycache__/*") { return $true }
    if ($normalized -like ".pytest_cache/*" -or $normalized -like "*/.pytest_cache/*") { return $true }
    if ($normalized -like "reports/_unit_test_tmp/*") { return $true }
    if ($normalized -match "(^|/)reports/[^/]*_unit_test_tmp[^/]*/") { return $true }
    if ($normalized -like "*.pyc") { return $true }
    return $false
}

function Get-PublishFiles {
    param([string]$Root)
    $base = (Resolve-Path -LiteralPath $Root).Path
    $files = New-Object System.Collections.Generic.List[object]
    Get-ChildItem -LiteralPath $base -Recurse -File -Force | ForEach-Object {
        $relative = $_.FullName.Substring($base.Length).TrimStart("\")
        if (Test-ExcludedRelativePath -RelativePath $relative) {
            return
        }
        $files.Add([PSCustomObject]@{
            FullName = $_.FullName
            Path = ($relative -replace "\\", "/")
            Length = $_.Length
        })
    }
    return $files | Sort-Object Path
}

$source = Resolve-Path -LiteralPath $SourcePath
$files = @(Get-PublishFiles -Root $source.Path)
$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum

Write-Host "publish_source=$($source.Path)"
Write-Host "publish_file_count=$($files.Count)"
Write-Host "publish_total_mb=$([Math]::Round($totalBytes / 1MB, 2))"

if ($DryRun) {
    $files | Select-Object -First 20 Path, Length | Format-Table -AutoSize
    if ($files.Count -gt 20) {
        Write-Host "... $($files.Count - 20) more files"
    }
    exit 0
}

$token = Get-GitHubToken -Name $TokenEnvName
$headers = New-GitHubHeaders -Token $token
$apiBase = "https://api.github.com/repos/$Owner/$Repo"

$repoInfo = Invoke-GitHubJson -Method GET -Uri $apiBase -Headers $headers
Write-Host "target_repo=$($repoInfo.full_name)"

$refReadUri = "$apiBase/git/ref/heads/$Branch"
$refWriteUri = "$apiBase/git/refs/heads/$Branch"
$ref = Invoke-GitHubJson -Method GET -Uri $refReadUri -Headers $headers -AllowNotFound
$parentSha = $null
if ($ref) {
    $parentSha = $ref.object.sha
    if (-not $AllowReplaceRemoteTree) {
        throw "Remote branch '$Branch' already exists at $parentSha. Re-run with -AllowReplaceRemoteTree if replacing its tree is intended."
    }
    Write-Host "remote_parent=$parentSha"
}
else {
    Write-Host "remote_parent=<none>"
    $bootstrap = Invoke-GitHubJson -Method PUT -Uri "$apiBase/contents/.ompcp_bootstrap" -Headers $headers -Body @{
        message = "Bootstrap empty OMPCP repository"
        content = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("bootstrap`n"))
        branch = $Branch
    }
    $parentSha = $bootstrap.commit.sha
    $ref = [PSCustomObject]@{ object = [PSCustomObject]@{ sha = $parentSha } }
    Write-Host "bootstrap_parent=$parentSha"
}

$treeEntries = New-Object System.Collections.Generic.List[object]
$counter = 0
foreach ($file in $files) {
    $counter++
    if ($counter % 50 -eq 0) {
        Write-Host "uploaded_blobs=$counter/$($files.Count)"
    }
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    $content = [Convert]::ToBase64String($bytes)
    $blob = Invoke-GitHubJson -Method POST -Uri "$apiBase/git/blobs" -Headers $headers -Body @{
        content = $content
        encoding = "base64"
    }
    $treeEntries.Add(@{
        path = $file.Path
        mode = "100644"
        type = "blob"
        sha = $blob.sha
    })
}

$tree = Invoke-GitHubJson -Method POST -Uri "$apiBase/git/trees" -Headers $headers -Body @{
    tree = @($treeEntries)
}
Write-Host "tree_sha=$($tree.sha)"

$commitBody = @{
    message = $CommitMessage
    tree = $tree.sha
}
if ($parentSha) {
    $commitBody.parents = @($parentSha)
}
$commit = Invoke-GitHubJson -Method POST -Uri "$apiBase/git/commits" -Headers $headers -Body $commitBody
Write-Host "commit_sha=$($commit.sha)"

if ($ref) {
    Invoke-GitHubJson -Method PATCH -Uri $refWriteUri -Headers $headers -Body @{
        sha = $commit.sha
        force = $false
    } | Out-Null
}
else {
    Invoke-GitHubJson -Method POST -Uri "$apiBase/git/refs" -Headers $headers -Body @{
        ref = "refs/heads/$Branch"
        sha = $commit.sha
    } | Out-Null
}

Write-Host "published=https://github.com/$Owner/$Repo/tree/$Branch"
