param(
    [Parameter(Mandatory=$true)]
    [string]$ArtifactId,
    [Parameter(Mandatory=$true)]
    [string]$OutputPath,
    [string]$SecretPath = "C:\codex-data\OMPCP_secrets\github_token.clixml"
)

$ErrorActionPreference = "Stop"

function Convert-SecureStringToPlainText {
    param([securestring]$SecureValue)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

if (-not (Test-Path -LiteralPath $SecretPath)) {
    throw "Secure token file does not exist: $SecretPath"
}

$secureToken = Import-Clixml -Path $SecretPath
if (-not ($secureToken -is [securestring])) {
    throw "Secret file did not contain a SecureString."
}

$plainToken = Convert-SecureStringToPlainText -SecureValue $secureToken
if (-not $plainToken) {
    throw "Secure token decrypted to an empty value."
}

try {
    $env:GITHUB_TOKEN = $plainToken
    $downloader = "C:\codex-data\OMPCP\scripts\download_github_actions_artifact_node.mjs"
    & node $downloader --artifact-id $ArtifactId --output-path $OutputPath
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
    $plainToken = $null
    [GC]::Collect()
}
