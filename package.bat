@echo off

chcp 65001 >nul

REM 배포 ZIP은 scripts\pack_dist.ps1 과 동일 규칙^(버전 폴더 cafescraper_Vx.y.z, data 제외^)을 씁니다.

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack_dist.ps1"

set ERR=%ERRORLEVEL%

if %ERR% neq 0 (

    pause

    exit /b %ERR%

)

pause

exit /b 0

