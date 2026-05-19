# PyInstaller COLLECT 폴더명 = cafescraper_V{semver} (cafescraper.spec가 version.txt에서 생성)
# 배포 ZIP: 프로젝트 루트 version.txt 기준 -> cafescraper_V{semver}.zip (ASCII)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

$verFile = Join-Path $root 'version.txt'
if (-not (Test-Path -LiteralPath $verFile)) {
    Write-Error "version.txt 가 없습니다. 프로젝트 루트에 예: 1.3.1 한 줄로 두세요."
    exit 2
}
$ver = (Get-Content -LiteralPath $verFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($ver)) {
    Write-Error "version.txt 내용이 비어 있습니다."
    exit 2
}
# 파일명에 쓰이면 안 되는 문자 제거(semver만 가정)
$verSafe = $ver -replace '[^0-9A-Za-z._-]', ''
if ($verSafe -ne $ver) {
    Write-Error "version.txt 에는 배포 파일명에 쓸 수 있는 문자만 넣어주세요. (현재: '$ver')"
    exit 2
}

$distFolder = "cafescraper_V${verSafe}"
$distDir = [System.IO.Path]::Combine($root, 'dist', $distFolder)
$exePath = Join-Path $distDir 'CafeScraper.exe'
$zipName = "cafescraper_V${verSafe}.zip"
$zipPath = Join-Path $root $zipName
$minZipBytes = 35MB

if (-not (Test-Path -LiteralPath $exePath)) {
    Write-Error "dist\$distFolder\CafeScraper.exe 가 없습니다. 먼저 build.bat ^(또는 pyinstaller cafescraper.spec^)을 실행하세요."
    exit 2
}

# 배포 ZIP에는 사용자 DB·설정이 들어 있는 항목을 넣지 않음 (빌드 직전 복원된 dist 대비).
# - data/: SQLite 등
# - crawler_config.json: 로컬 계정/경로 (개발자 테스트 복원본이 그대로 들어가면 유출 위험)
$items = @(Get-ChildItem -LiteralPath $distDir -Force | Where-Object {
        $n = $_.Name
        ($n -ine 'data') -and ($n -ine 'crawler_config.json') -and ($n -ine 'comment_templates.json')
    })
if ($items.Count -lt 1) {
    Write-Error "dist\$distFolder 내용이 비정상적으로 적습니다. (data 제외 항목 수: $($items.Count))"
    exit 2
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
    if (Test-Path -LiteralPath $zipPath) {
        Write-Error "기존 ZIP 파일을 삭제할 수 없습니다. 파일이 다른 프로그램에서 열려있는지 확인하세요."
        exit 2
    }
}

function Invoke-PackToZip {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileSystemInfo[]]$Items,
        [Parameter(Mandatory = $true)]
        [string]$DestZip
    )
    if ($Items.Count -lt 1) {
        throw "No items to pack"
    }
    Compress-Archive -LiteralPath ($Items.FullName) -DestinationPath $DestZip -Force
}

# PyInstaller/AV sometimes locks _internal\*.zip briefly after COLLECT; wait + retries, then staging copy fallback.
$maxAttempts = 6
$sleepSec = 3
$packed = $false
Write-Host "Waiting ${sleepSec}s before ZIP (avoid file lock on fresh build)..."
Start-Sleep -Seconds $sleepSec
for ($a = 1; $a -le $maxAttempts; $a++) {
    try {
        Invoke-PackToZip -Items $items -DestZip $zipPath
        $packed = $true
        break
    } catch {
        Write-Warning "ZIP attempt $a/$maxAttempts failed: $($_.Exception.Message)"
        if ($a -lt $maxAttempts) { Start-Sleep -Seconds $sleepSec }
    }
}
if (-not $packed) {
    $stage = Join-Path $env:TEMP ("cafescraper_pack_" + [guid]::NewGuid().ToString('N'))
    Write-Host "Falling back: copy to staging folder then ZIP: $stage"
    try {
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        robocopy $distDir $stage /E /XD data /XF crawler_config.json comment_templates.json /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed with exit $LASTEXITCODE"
        }
        $stageItems = @(Get-ChildItem -LiteralPath $stage -Force)
        Invoke-PackToZip -Items $stageItems -DestZip $zipPath
        $packed = $true
    } finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
if (-not $packed) {
    Write-Error "ZIP failed after retries and staging copy. Close CafeScraper.exe, pause antivirus, or retry."
    exit 5
}

$stat = Get-Item -LiteralPath $zipPath
if ($stat.Length -lt $minZipBytes) {
    Write-Error "ZIP 용량이 비정상적으로 작습니다 ($($stat.Length) bytes). 압축이 실패했을 수 있습니다."
    exit 3
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipRead = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $hasExe = $false
    foreach ($e in $zipRead.Entries) {
        if ($e.Name -eq 'CafeScraper.exe') {
            $hasExe = $true
            break
        }
    }
    if (-not $hasExe) {
        Write-Error "ZIP 안에 CafeScraper.exe 가 없습니다. 압축 경로를 확인하세요."
        exit 4
    }
} finally {
    $zipRead.Dispose()
}

$mb = [math]::Round($stat.Length / 1MB, 2)
Write-Host "VERSION=$verSafe"
Write-Host "OK: $($stat.FullName) (${mb} MB)"
Write-Host "DIST_FOLDER=$distDir"
Write-Host "SHIP_ZIP=$zipPath"
