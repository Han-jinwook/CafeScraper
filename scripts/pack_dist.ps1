# CafeScraper: dist\CafeScraper 내용물 → 프로젝트 루트 CafeScraper_배포.zip (검증 포함)
# build.bat에서 PyInstaller 성공 후 호출.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

$distDir = Join-Path $root 'dist\cafescraper'
$exePath = Join-Path $distDir 'CafeScraper.exe'
$zipPath = Join-Path $root 'CafeScraper_배포.zip'
$minZipBytes = 35MB

if (-not (Test-Path -LiteralPath $exePath)) {
    Write-Error "dist\CafeScraper\CafeScraper.exe 가 없습니다. PyInstaller 단계를 확인하세요."
    exit 2
}

$items = @(Get-ChildItem -LiteralPath $distDir -Force)
if ($items.Count -lt 2) {
    Write-Error "dist\cafescraper 내용이 비정상적으로 적습니다. (항목 수: $($items.Count))"
    exit 2
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
    if (Test-Path -LiteralPath $zipPath) {
        Write-Error "기존 ZIP 파일을 삭제할 수 없습니다. 파일이 다른 프로그램에서 열려있는지 확인하세요."
        exit 2
    }
}

# 폴더 *내용*을 ZIP 루트에 두기 (압축 해제 후 바로 CafeScraper.exe 노출)
Compress-Archive -LiteralPath ($items.FullName) -DestinationPath $zipPath -Force

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
Write-Host "OK: $($stat.FullName) (${mb} MB)"
