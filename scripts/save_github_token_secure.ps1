param(
    [string]$SecretPath = "C:\codex-data\OMPCP_secrets\github_token.clixml"
)

$ErrorActionPreference = "Stop"

$secretFile = [System.IO.FileInfo]::new($SecretPath)
if (-not $secretFile.Directory.Exists) {
    New-Item -ItemType Directory -Path $secretFile.Directory.FullName -Force | Out-Null
}

Write-Host "Paste the GitHub token at the hidden prompt. It will be stored with Windows DPAPI for the current Windows user."
$secureToken = Read-Host "GitHub token" -AsSecureString

if ($secureToken.Length -eq 0) {
    throw "Empty token was not saved."
}

$secureToken | Export-Clixml -Path $secretFile.FullName

Write-Host "saved_secret=$($secretFile.FullName)"
Write-Host "note=The plaintext token was not written to command history, scripts, Git files, or logs."
