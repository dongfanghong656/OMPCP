param(
    [string]$SecretPath = "C:\codex-data\OMPCP_secrets\github_token.clixml",
    [string]$SourcePath = "C:\codex-data\OMPCP",
    [ValidateSet("node", "powershell")]
    [string]$Publisher = "node",
    [switch]$AllowReplaceRemoteTree,
    [switch]$DryRun
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
    throw "Secure token file does not exist: $SecretPath. Run scripts\save_github_token_secure.ps1 first."
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
    if ($Publisher -eq "node") {
        $nodePublisher = "C:\codex-data\OMPCP\scripts\publish_ompcp_via_github_api_node.mjs"
        if (-not (Test-Path -LiteralPath $nodePublisher)) {
            throw "Node publisher does not exist: $nodePublisher"
        }
        $nodeArgs = @(
            $nodePublisher,
            "--source-path", $SourcePath
        )
        if ($AllowReplaceRemoteTree) {
            $nodeArgs += "--allow-replace-remote-tree"
        }
        if ($DryRun) {
            $nodeArgs += "--dry-run"
        }
        & node @nodeArgs
    }
    else {
        $powershellPublisher = "C:\codex-data\OMPCP\scripts\publish_ompcp_via_github_api.ps1"
        $publisherArgs = @{
            SourcePath = $SourcePath
        }
        if ($AllowReplaceRemoteTree) {
            $publisherArgs.AllowReplaceRemoteTree = $true
        }
        if ($DryRun) {
            $publisherArgs.DryRun = $true
        }
        & $powershellPublisher @publisherArgs
    }
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
    $plainToken = $null
    [GC]::Collect()
}
