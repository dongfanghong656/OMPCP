param(
    [string]$SecretPath = "C:\codex-data\OMPCP_secrets\github_token.clixml",
    [string]$SourcePath = "C:\codex-data\OMPCP",
    [Parameter(Mandatory=$true)]
    [string[]]$Path,
    [string]$CommitMessage = "Harden pytmatrix CI runtime DLL packaging"
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
    $publisher = "C:\codex-data\OMPCP\scripts\publish_ompcp_incremental_via_github_api_node.mjs"
    $args = @($publisher, "--source-path", $SourcePath, "--commit-message", $CommitMessage)
    foreach ($item in $Path) {
        $args += @("--path", $item)
    }
    & node @args
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
    $plainToken = $null
    [GC]::Collect()
}
