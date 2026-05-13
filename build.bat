@echo off
REM English only: avoids cmd.exe encoding issues.
cd /d "%~dp0"

echo ============================================
echo   CafeScraper - PyInstaller + versioned ZIP
echo ============================================
echo.
echo [REMINDER] Bump version.txt before each build ^(patch +1: 1.3.5 -^> 1.3.6^).
echo.

if not exist "%~dp0version.txt" (
    echo [ERROR] version.txt is missing in project root.
    exit /b 1
)

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/5] Installing PyInstaller...
    pip install pyinstaller
) else (
    echo [1/5] PyInstaller OK
)

echo [2/5] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist\CafeScraper rmdir /s /q dist\CafeScraper
if exist dist\CafeScraper.zip del /f /q dist\CafeScraper.zip
if exist CafeScraper_release.zip del /f /q CafeScraper_release.zip

REM Same version as version.txt: remove only that zip so older cafescraper_V* are kept.
setlocal EnableDelayedExpansion
set "RELVER="
for /f "usebackq delims=" %%a in ("%~dp0version.txt") do (
    set "RELVER=%%a"
    goto :ver_done
)
:ver_done
set "RELVER=!RELVER: =!"
if defined RELVER if exist "cafescraper_V!RELVER!.zip" del /f /q "cafescraper_V!RELVER!.zip"
endlocal

echo [3/5] PyInstaller build...
echo.
pyinstaller cafescraper.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

if not exist "dist\CafeScraper" (
    echo.
    echo [ERROR] dist\CafeScraper folder not found.
    exit /b 1
)

if not exist "dist\CafeScraper\CafeScraper.exe" (
    echo.
    echo [ERROR] dist\CafeScraper\CafeScraper.exe not found.
    exit /b 1
)

echo.
echo [4/5] Creating cafescraper_VVERSION.zip from version.txt...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack_dist.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] ZIP step failed - see scripts\pack_dist.ps1 output.
    exit /b 1
)

echo.
echo [5/5] Done
echo ============================================
echo   EXE folder:  dist\CafeScraper\
echo   Version:     see version.txt
echo   Ship ZIP:    cafescraper_V^<version^>.zip in project root
echo ============================================

exit /b 0
