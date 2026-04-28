param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,

    [Parameter(Mandatory = $true)]
    [string]$PdfPath,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$Year,

    [string]$Authors = "",
    [string]$SourceTag = "local-pdf",
    [switch]$Translate,
    [ValidateSet("ai", "manual")]
    [string]$TranslationMode = "manual",
    [string]$TranslationFile = ""
)

$ErrorActionPreference = "Stop"

function New-CompactSlug {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [int]$MaxLength = 40,
        [string]$Fallback = "paper"
    )

    $slug = $Value.ToLowerInvariant() -replace '[^a-z0-9]+', '-'
    $slug = $slug.Trim('-')
    if (-not $slug) {
        $hashSource = if ($Value) { $Value } else { $Fallback }
        $sha1 = [System.Security.Cryptography.SHA1]::Create()
        try {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($hashSource)
            $hash = [System.BitConverter]::ToString($sha1.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant().Substring(0, 8)
        } finally {
            $sha1.Dispose()
        }
        $slug = "$Fallback-$hash"
    }
    if ($slug.Length -le $MaxLength) {
        return $slug
    }

    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($slug)
        $hash = [System.BitConverter]::ToString($sha1.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant().Substring(0, 8)
    } finally {
        $sha1.Dispose()
    }
    $prefixLength = [Math]::Max(8, $MaxLength - $hash.Length - 1)
    $prefix = $slug.Substring(0, [Math]::Min($prefixLength, $slug.Length)).Trim('-')
    if (-not $prefix) {
        return $hash.Substring(0, [Math]::Min($hash.Length, $MaxLength))
    }
    return "$prefix-$hash"
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configAbs = (Resolve-Path $ConfigPath).Path
$pdfAbs = (Resolve-Path $PdfPath).Path
$config = Get-Content -Raw $configAbs | ConvertFrom-Json

python (Join-Path $scriptRoot "bootstrap_vault.py") --config $configAbs | Out-Host

$safeStem = New-CompactSlug -Value "$Year-$Title" -MaxLength 32 -Fallback "paper"
$extractRoot = Join-Path $config.vault_root ("08_Attachments\\extracted\\" + $safeStem)
$extractMd = ""
$translatedNotePath = ""
$translationTemplatePath = ""

try {
    powershell -ExecutionPolicy Bypass -File $config.mineru_runner -InputPath $pdfAbs -OutputDir $extractRoot | Out-Host
    $extractMdCandidate = Get-ChildItem -Path $extractRoot -Recurse -File -Include *.md -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($extractMdCandidate) {
        $extractMd = $extractMdCandidate.FullName
    }
} catch {
    Write-Warning ("MinerU extraction failed: " + $_.Exception.Message)
}

if ($Translate -and $extractMd) {
    try {
        if ($TranslationMode -eq "manual" -and -not $TranslationFile) {
            $prepareArgs = @(
                (Join-Path $scriptRoot "translate_paper.py"),
                "prepare",
                "--config", $configAbs,
                "--extract-path", $extractMd,
                "--title", $Title,
                "--year", $Year,
                "--target-language", "zh-CN",
                "--source-pdf", $pdfAbs
            )
            if ($Authors) {
                $prepareArgs += @("--authors", $Authors)
            }
            $prepareResult = python @prepareArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to prepare manual translation template."
            }
            $prepareJson = $prepareResult | ConvertFrom-Json
            $translationTemplatePath = $prepareJson.template_path
        } else {
            $buildArgs = @(
                (Join-Path $scriptRoot "translate_paper.py"),
                "build",
                "--config", $configAbs,
                "--extract-path", $extractMd,
                "--title", $Title,
                "--year", $Year,
                "--target-language", "zh-CN",
                "--source-pdf", $pdfAbs,
                "--mode", $TranslationMode
            )
            if ($Authors) {
                $buildArgs += @("--authors", $Authors)
            }
            if ($TranslationFile) {
                $buildArgs += @("--translation-file", (Resolve-Path $TranslationFile).Path)
            }
            $buildResult = python @buildArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to build translated paper."
            }
            $buildJson = $buildResult | ConvertFrom-Json
            $translatedNotePath = $buildJson.translated_note_path
        }
    } catch {
        Write-Warning ("Translation pipeline failed: " + $_.Exception.Message)
    }
} elseif ($Translate) {
    Write-Warning "Translation requested but MinerU did not produce a markdown extract."
}

$seedArgs = @(
    (Join-Path $scriptRoot "seed_paper_note.py"),
    "--config", $configAbs,
    "--pdf-path", $pdfAbs,
    "--title", $Title,
    "--year", $Year,
    "--source-tag", $SourceTag,
    "--copy-pdf"
)

if ($Authors) {
    $seedArgs += @("--authors", $Authors)
}

if ($extractMd) {
    $seedArgs += @("--extract-path", $extractMd)
}

if ($translatedNotePath) {
    $seedArgs += @("--translated-note-path", $translatedNotePath)
}

if ($translationTemplatePath) {
    $seedArgs += @("--translation-template-path", $translationTemplatePath)
}

python @seedArgs | Out-Host
