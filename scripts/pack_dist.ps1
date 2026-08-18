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

$distFolder = [System.IO.Path]::Combine("CafeMonster-V${verSafe}", "cafescraper_V${verSafe}")
$distDir = [System.IO.Path]::Combine($root, 'dist', $distFolder)
$exePath = Join-Path $distDir 'CafeScraper.exe'
$minZipBytes = 35MB

if (-not (Test-Path -LiteralPath $exePath)) {
    Write-Error "dist\$distFolder\CafeScraper.exe 가 없습니다. 먼저 build.bat ^(또는 pyinstaller cafescraper.spec^)을 실행하세요."
    exit 2
}

# 배포 ZIP에는 사용자 DB·설정이 들어 있는 항목을 넣지 않음 (빌드 직전 복원된 dist 대비).
# - data/: SQLite 등
# - user_settings.json / crawler_config.json: 로컬 계정/경로 (개발자 테스트 복원본이 그대로 들어가면 유출 위험)
$items = @(Get-ChildItem -LiteralPath $distDir -Force | Where-Object {
        $n = $_.Name
        ($n -ine 'data') -and ($n -ine 'crawler_config.json') -and ($n -ine 'user_settings.json') -and ($n -ine 'comment_templates.json')
    })
if ($items.Count -lt 1) {
    Write-Error "dist\$distFolder 내용이 비정상적으로 적습니다. (data 제외 항목 수: $($items.Count))"
    exit 2
}

# Clean up previously generated product zips if they exist
$targets = @(
    "CafeCrawler-Pro.zip",
    "EventStats-Pro.zip",
    "AutoComment-Pro.zip",
    "CafeMonster-Trial.zip"
)

foreach ($t in $targets) {
    $zipPath = [System.IO.Path]::Combine($root, 'dist', "CafeMonster-V${verSafe}", $t)
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
        if (Test-Path -LiteralPath $zipPath) {
            Write-Error "기존 ZIP 파일($t)을 삭제할 수 없습니다. 파일이 잠겨 있는지 확인하세요."
            exit 2
        }
    }
}
function Invoke-PackToZip {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestZip
    )
    # Use python's shutil.make_archive for ultra-fast, 100% Windows Explorer compatible zipping
    $zipBase = $DestZip -replace '\.zip$', ''
    python -c "import shutil; shutil.make_archive(r'$zipBase', 'zip', r'$SourceDir')"
}
# Wait to avoid file locks
$sleepSec = 3
Write-Host "Waiting ${sleepSec}s before ZIP (avoid file lock on fresh build)..."
Start-Sleep -Seconds $sleepSec

# Define the package jobs to run
# Format: @{ Name = "output_zip"; Mode = "PRO_CAFECRAWLER" | "PRO_EVENTSTATS" | "PRO_AUTOCOMMENT" | "TRIAL" }
$jobs = @(
    @{ Name = "CafeCrawler-Pro.zip"; Mode = "PRO_CAFECRAWLER" },
    @{ Name = "EventStats-Pro.zip"; Mode = "PRO_EVENTSTATS" },
    @{ Name = "AutoComment-Pro.zip"; Mode = "PRO_AUTOCOMMENT" },
    @{ Name = "CafeMonster-Trial.zip"; Mode = "TRIAL" }
)

# Package each job
foreach ($job in $jobs) {
    $zipName = $job.Name
    $parentDir = [System.IO.Path]::Combine($root, 'dist', "CafeMonster-V${verSafe}")
    if (-not (Test-Path -LiteralPath $parentDir)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }
    $zipPath = [System.IO.Path]::Combine($parentDir, $zipName)
    
    # Create unique staging folder
    $stage = Join-Path $env:TEMP ("cafescraper_pack_" + [guid]::NewGuid().ToString('N'))
    Write-Host "[PACK] Staging $zipName -> $stage"
    
    try {
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        
        # Copy build to staging
        robocopy $distDir $stage /E /XD data /XF crawler_config.json user_settings.json comment_templates.json /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed with exit $LASTEXITCODE"
        }
        
        # Write mode.txt inside staging directory (use ascii to avoid BOM in PowerShell 5.1)
        $modeText = $job.Mode.ToUpper()
        Set-Content -Path (Join-Path $stage "mode.txt") -Value $modeText -Encoding ascii
        
        # Pack staging to target ZIP using tar.exe
        Invoke-PackToZip -SourceDir $stage -DestZip $zipPath
        
        # Verify ZIP integrity
        $stat = Get-Item -LiteralPath $zipPath
        if ($stat.Length -lt $minZipBytes) {
            Write-Error "ZIP 용량이 비정상적으로 작습니다 (${zipName}: $($stat.Length) bytes)."
            exit 3
        }
        
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zipRead = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
        try {
            $hasExe = $false
            foreach ($entry in $zipRead.Entries) {
                if ($entry.Name -eq 'CafeScraper.exe') {
                    $hasExe = $true
                    break
                }
            }
            if (-not $hasExe) {
                Write-Error "ZIP($zipName) 안에 CafeScraper.exe 가 없습니다."
                exit 4
            }
        } finally {
            $zipRead.Dispose()
        }
        
        $mb = [math]::Round($stat.Length / 1MB, 2)
        Write-Host "[OK] Created: $zipName (${mb} MB)"
        
    } finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
        }
    }
}

Write-Host "VERSION=$verSafe"
Write-Host "All 4 package ZIPs successfully created in dist folder!"
