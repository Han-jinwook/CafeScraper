@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   CafeScraper EXE 빌드 + 배포 ZIP (검증 포함)
echo ============================================
echo.

:: PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/5] PyInstaller 설치 중...
    pip install pyinstaller
) else (
    echo [1/5] PyInstaller 확인 완료
)

:: 기존 빌드 정리 (PyInstaller workpath는 보통 build\spec이름\ 이므로 build 전체 삭제)
echo [2/5] 이전 빌드 정리...
if exist build rmdir /s /q build
if exist dist\cafescraper rmdir /s /q dist\cafescraper
if exist CafeScraper_배포.zip del /f /q CafeScraper_배포.zip

:: 빌드 실행
echo [3/5] PyInstaller 빌드 (수 분 소요)...
echo.
pyinstaller cafescraper.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller 실패! 위 메시지를 확인하세요.
    pause
    exit /b 1
)

if not exist "dist\cafescraper\CafeScraper.exe" (
    echo.
    echo [ERROR] dist\cafescraper\CafeScraper.exe 가 없습니다.
    pause
    exit /b 1
)

:: 배포 ZIP: 압축 + 용량·내부 exe 검증 (scripts\pack_dist.ps1)
echo.
echo [4/5] 배포용 ZIP 생성 및 검증...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack_dist.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] ZIP 생성 또는 검증 실패 (scripts\pack_dist.ps1 출력 확인).
    pause
    exit /b 1
)

echo.
echo [5/5] 완료 확인
echo ============================================
echo   완료!
echo   - 실행 폴더: dist\cafescraper\
echo   - 배포 ZIP:  CafeScraper_배포.zip  ^(루트에 생성, 검증됨^)
echo ============================================
echo.
echo ZIP만 배포하거나, dist\cafescraper 폴더 통째로 복사해도 됩니다.
echo.
pause
