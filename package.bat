@echo off
chcp 65001 >nul
echo ============================================
echo   CafeScraper 배포 ZIP 생성
echo ============================================
echo.

if not exist "dist\CafeScraper\CafeScraper.exe" (
    echo [ERROR] dist\CafeScraper\CafeScraper.exe 가 없습니다.
    echo         먼저 build.bat 를 실행하세요.
    pause
    exit /b 1
)

:: ZIP 파일명 (날짜 포함)
for /f "tokens=1-3 delims=/" %%a in ('date /t') do set TODAY=%%a%%b%%c
set ZIPNAME=CafeScraper_%TODAY%.zip

:: 기존 zip 삭제
if exist "%ZIPNAME%" del "%ZIPNAME%"

echo ZIP 압축 중... (1~2분 소요)
powershell -Command "Compress-Archive -Path 'dist\CafeScraper\*' -DestinationPath '%ZIPNAME%' -Force"

if errorlevel 1 (
    echo [ERROR] 압축 실패!
    pause
    exit /b 1
)

for %%A in ("%ZIPNAME%") do set ZIPSIZE=%%~zA
set /a ZIPSIZE_MB=%ZIPSIZE% / 1048576

echo.
echo ============================================
echo   완료: %ZIPNAME% (%ZIPSIZE_MB% MB)
echo ============================================
echo.
echo 이 ZIP 파일을 Google Drive/USB에 올리고
echo 다른 PC에서 압축 풀고 CafeScraper.exe 실행!
echo.
pause
