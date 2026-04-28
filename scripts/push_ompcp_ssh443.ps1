param(
    [string]$RepoPath = "C:\codex-data\OMPCP_pushable_latest",
    [string]$Remote = "ssh://git@ssh.github.com:443/dongfanghong656/OMPCP.git",
    [string]$Branch = "main",
    [string]$SshKey = "C:\codex-data\OMPCP_github_deploy_ed25519",
    [string]$KnownHosts = "C:\codex-data\OMPCP_github_known_hosts"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}
if (-not (Test-Path -LiteralPath $SshKey)) {
    throw "SSH key does not exist: $SshKey"
}
if (-not (Test-Path -LiteralPath $KnownHosts)) {
    New-Item -ItemType File -Path $KnownHosts -Force | Out-Null
    & C:\Windows\System32\OpenSSH\ssh.exe `
        -T `
        -o BatchMode=yes `
        -o IdentitiesOnly=yes `
        -o StrictHostKeyChecking=accept-new `
        -o UserKnownHostsFile=$KnownHosts `
        -i $SshKey `
        -p 443 `
        git@ssh.github.com | Out-Null
}

$env:GIT_SSH = "C:\codex-data\OMPCP\scripts\git_ssh_443_ompcp.cmd"
$env:GIT_SSH_VARIANT = "ssh"

$currentRemote = git -C $RepoPath remote get-url origin
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
if ($currentRemote -ne $Remote) {
    throw "Unexpected origin remote '$currentRemote'. Expected '$Remote'. Recreate the pushable repo instead of editing .git/config in this sandbox."
}

git -C $RepoPath push -u origin $Branch
exit $LASTEXITCODE
