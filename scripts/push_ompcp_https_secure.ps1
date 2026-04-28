param(
    [string]$RepoPath = "C:\codex-data\OMPCP_pushable_latest",
    [string]$RemoteUrl = "https://github.com/dongfanghong656/OMPCP.git",
    [string]$Branch = "main",
    [switch]$ForceWithLease
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path -LiteralPath $RepoPath
$askpass = "C:\codex-data\OMPCP\scripts\git_askpass_secure.cmd"
if (-not (Test-Path -LiteralPath $askpass)) {
    throw "Missing askpass helper: $askpass"
}

$env:GIT_ASKPASS = $askpass
$env:GIT_TERMINAL_PROMPT = "0"
$env:GIT_OPTIONAL_LOCKS = "0"
try {
    $pushArgs = @("-C", $repo.Path, "push", $RemoteUrl, "${Branch}:${Branch}")
    if ($ForceWithLease) {
        $pushArgs = @("-C", $repo.Path, "push", "--force-with-lease", $RemoteUrl, "${Branch}:${Branch}")
    }
    & git @pushArgs
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:GIT_ASKPASS -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_OPTIONAL_LOCKS -ErrorAction SilentlyContinue
}
