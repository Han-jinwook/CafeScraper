@echo off
chcp 65001 >nul
echo ============================================
echo   CafeScraper EXE 빌드
echo ============================================
echo.

:: PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] PyInstaller 설치 중...
    pip install pyinstaller
) else (
    echo [1/3] PyInstaller 확인 완료
)

:: 기존 빌드 정리
echo [2/3] 이전 빌드 정리...
if exist dist\CafeScraper rmdir /s /q dist\CafeScraper
if exist build\CafeScraper rmdir /s /q build\CafeScraper

:: 빌드 실행
echo [3/3] 빌드 시작 (2~5분 소요)...
echo.
pyinstaller cafescraper.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] 빌드 실패! 위 에러 메시지를 확인하세요.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   빌드 완료!
echo   결과: dist\CafeScraper\CafeScraper.exe
echo ============================================
echo.
echo dist\CafeScraper 폴더를 통째로 복사하면
echo 어디서든 CafeScraper.exe 더블클릭으로 실행됩니다.
echo.
pause
