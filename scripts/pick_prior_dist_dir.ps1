# CafeScraper build helper: choose dist\cafescraper_V*- folder to migrate user data FROM
# when version.txt bumped (target distfolder does not exist yet or is empty).
# Args: $DistRootPath  $CurrentFolderName e.g. "cafescraper_V1.3.12"
# Stdout: one absolute path or nothing.

param(
    [Parameter(Mandatory = $true)][string]$DistRootPath,
    [Parameter(Mandatory = $true)][string]$CurrentFolderName
)

$rootItem = Get-Item -LiteralPath $DistRootPath -ErrorAction SilentlyContinue
if (-not $rootItem -or -not ($rootItem -is [System.IO.DirectoryInfo])) {
    exit 0
}

$rootPath = $rootItem.FullName
$candidates = @()

foreach ($d in Get-ChildItem -LiteralPath $rootPath -Directory -ErrorAction SilentlyContinue) {
    if ($d.Name -eq $CurrentFolderName) {
        continue
    }
    if ($d.Name -notmatch '^cafescraper_V(\d+)\.(\d+)\.(\d+)$') {
        continue
    }

    try {
        $ver = [System.Version]::new([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
    } catch {
        continue
    }

    $jp = Join-Path $d.FullName 'crawler_config.json'
    $us = Join-Path $d.FullName 'user_settings.json'
    $tpl = Join-Path $d.FullName 'comment_templates.json'
    $dat = Join-Path $d.FullName 'data'
    $sess = Join-Path $d.FullName 'sessions'
    $snap = Join-Path $d.FullName 'snapshots'
    $hasPersist =
        ((Test-Path -LiteralPath $jp) -or
        (Test-Path -LiteralPath $us) -or
        (Test-Path -LiteralPath $tpl) -or
        (Test-Path -LiteralPath $dat) -or
        (Test-Path -LiteralPath $sess) -or
        (Test-Path -LiteralPath $snap))

    if (-not $hasPersist) {
        continue
    }

    $candidates += [pscustomobject]@{
        FullName = $d.FullName
        Version  = $ver
    }
}

if ($candidates.Count -eq 0) {
    exit 0
}

$picked =
    $candidates |
    Sort-Object @{ Expression = 'Version'; Descending = $true },
        @{ Expression = 'FullName'; Ascending = $true } |
    Select-Object -First 1

Write-Output $picked.FullName
exit 0
