param(
    [string]$Prompt,
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

if ($Prompt -match "Username") {
    Write-Output "x-access-token"
    exit 0
}

if ($Prompt -match "Password") {
    $secureToken = Import-Clixml -Path $SecretPath
    if (-not ($secureToken -is [securestring])) {
        throw "Secret file did not contain a SecureString."
    }
    $plainToken = Convert-SecureStringToPlainText -SecureValue $secureToken
    try {
        Write-Output $plainToken
    }
    finally {
        $plainToken = $null
        [GC]::Collect()
    }
    exit 0
}

Write-Output ""
