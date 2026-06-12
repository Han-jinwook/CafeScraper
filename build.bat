@echo off

REM CafeScraper — PyInstaller local build (no ZIP). Bump version.txt on each release-worthy change.

REM English only in echoes: avoids cmd.exe encoding issues.

cd /d "%~dp0"



echo ============================================

echo   CafeScraper - PyInstaller (local test, no ZIP)

echo ============================================

echo.



if not exist "%~dp0version.txt" (

    echo [ERROR] version.txt is missing in project root.

    goto :fail_pause

)



set "DISTDIR="

for /f "usebackq tokens=* delims=" %%v in ("%~dp0version.txt") do (

    set "DISTDIR=cafescraper_V%%v"

    goto :have_distdir

)

:have_distdir

if not defined DISTDIR (

    echo [ERROR] Could not read version from version.txt.

    goto :fail_pause

)



echo [BUILD] Output folder: dist\%DISTDIR%\

echo [REMINDER] Bump version.txt + CHANGELOG before release: PATCH = last digit ^(small fixes^), MINOR = middle ^(bigger features/behavior^), MAJOR = first ^(breaking^).

echo.

if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [BUILD] Activating virtual environment .venv...
    call "%~dp0.venv\Scripts\activate.bat"
) else (
    echo [WARN] .venv virtual environment not found. Using system Python.
)

echo [BUILD] Patching Streamlit index.html in virtual environment to prevent ghost sidebar/skeleton...
python -c "import os; import streamlit; p = os.path.join(os.path.dirname(streamlit.__file__), 'static', 'index.html'); content = open(p, 'r', encoding='utf-8').read() if os.path.exists(p) else ''; style = '<style>[data-testid=\'stSidebar\'],section[data-testid=\'stSidebar\'],div[data-testid=\'stSidebar\'],[data-testid=\'collapsedControl\'],[data-testid=\'stSidebarNav\'],[data-testid=\'stSidebarNavItems\'],[data-testid=\'stSkeleton\']{display:none !important;min-width:0 !important;width:0 !important;}</style>'; new_content = content.replace('</head>', style + '</head>') if style not in content and '</head>' in content else content; open(p, 'w', encoding='utf-8').write(new_content) if new_content != content else None"

if not exist "%~dp0cafescraper.spec" (

    echo [ERROR] cafescraper.spec is missing in project root. PyInstaller needs it — check git/sparse-checkout.

    goto :fail_pause

)



pip show pyinstaller >nul 2>&1

if errorlevel 1 (

    echo [1/4] Installing PyInstaller...

    pip install pyinstaller

    if errorlevel 1 goto :fail_pause

) else (

    echo [1/4] PyInstaller OK

)



where pyinstaller >nul 2>&1

if errorlevel 1 (
    python -m PyInstaller --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] pyinstaller command not found. Install PyInstaller or fix PATH ^(same Python as pip^).
        goto :fail_pause
    ) else (
        echo PyInstaller found via python -m PyInstaller
        set "PYINSTALLER_CMD=python -m PyInstaller"
    )
) else (
    set "PYINSTALLER_CMD=pyinstaller"
)



echo [2/4] Cleaning previous build...

echo IMPORTANT: Close CafeScraper.exe ^(any dist folder^) before continuing.



REM Persisted user state lives next to the EXE (not only data\*.db):
REM - crawler_config.json — saved UI settings across all tabs
REM - comment_templates.json — 자동댓글러 저장 템플릿
REM - sessions\ — Selenium/profile cookies etc.
REM - snapshots\ — debug captures (optional)
REM Same-version rebuild: backup from dist\cafescraper_V{current}.
REM Semver bump: current folder often missing empty — backup from newest older dist\cafescraper_V* (see scripts\pick_prior_dist_dir.ps1).

set "SRCROOT="
if exist "%~dp0dist\%DISTDIR%\" set "SRCROOT=%~dp0dist\%DISTDIR%"

set "HASPERSIST=0"
if defined SRCROOT (
    if exist "%SRCROOT%\data" set "HASPERSIST=1"
    if exist "%SRCROOT%\crawler_config.json" set "HASPERSIST=1"
    if exist "%SRCROOT%\comment_templates.json" set "HASPERSIST=1"
    if exist "%SRCROOT%\sessions\" set "HASPERSIST=1"
    if exist "%SRCROOT%\snapshots\" set "HASPERSIST=1"
)

set "BK_SOURCE="
if "%HASPERSIST%"=="1" set "BK_SOURCE=%SRCROOT%"

set "PRIORROOT="
if not defined BK_SOURCE (
    for /f "usebackq tokens=* delims=" %%p in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pick_prior_dist_dir.ps1" "%~dp0dist" "%DISTDIR%"`) do set "PRIORROOT=%%p"
)

set "PRIORHAS=0"
if defined PRIORROOT (
    if exist "%PRIORROOT%\data" set "PRIORHAS=1"
    if exist "%PRIORROOT%\crawler_config.json" set "PRIORHAS=1"
    if exist "%PRIORROOT%\comment_templates.json" set "PRIORHAS=1"
    if exist "%PRIORROOT%\sessions\" set "PRIORHAS=1"
    if exist "%PRIORROOT%\snapshots\" set "PRIORHAS=1"
)
if "%PRIORHAS%"=="1" (
    echo [MIGRATE] semver bump — user state will be copied from prior folder:
    echo          "%PRIORROOT%"
    set "BK_SOURCE=%PRIORROOT%"
)

set LEG_LEGACY=%~dp0dist\CafeScraper
set "LEGHAS=0"
if exist "%LEG_LEGACY%\data\" set "LEGHAS=1"
if exist "%LEG_LEGACY%\crawler_config.json" set "LEGHAS=1"
if exist "%LEG_LEGACY%\comment_templates.json" set "LEGHAS=1"
if exist "%LEG_LEGACY%\sessions\" set "LEGHAS=1"
if exist "%LEG_LEGACY%\snapshots\" set "LEGHAS=1"

if "%LEGHAS%"=="1" if not defined BK_SOURCE (
    echo [MIGRATE] user state will be copied from legacy folder:
    echo          "%LEG_LEGACY%"
    set "BK_SOURCE=%LEG_LEGACY%"
)

if defined BK_SOURCE (
    echo Backing up user state from "%BK_SOURCE%" to dist\_user_data_backup ...

    if exist "%~dp0dist\_user_data_backup" rmdir /s /q "%~dp0dist\_user_data_backup"

    mkdir "%~dp0dist\_user_data_backup"

    if exist "%BK_SOURCE%\data\" (
        robocopy "%BK_SOURCE%\data" "%~dp0dist\_user_data_backup\data" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 (
            echo [ERROR] Backup failed ^(data^).
            goto :fail_pause
        )
    )

    if exist "%BK_SOURCE%\crawler_config.json" (
        copy /y "%BK_SOURCE%\crawler_config.json" "%~dp0dist\_user_data_backup\" >nul
        if errorlevel 1 (
            echo [ERROR] Backup failed ^(crawler_config.json^).
            goto :fail_pause
        )
    )

    if exist "%BK_SOURCE%\comment_templates.json" (
        copy /y "%BK_SOURCE%\comment_templates.json" "%~dp0dist\_user_data_backup\" >nul
        if errorlevel 1 (
            echo [ERROR] Backup failed ^(comment_templates.json^).
            goto :fail_pause
        )
    )

    if exist "%BK_SOURCE%\sessions\" (
        robocopy "%BK_SOURCE%\sessions" "%~dp0dist\_user_data_backup\sessions" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 (
            echo [ERROR] Backup failed ^(sessions^).
            goto :fail_pause
        )
    )

    if exist "%BK_SOURCE%\snapshots\" (
        robocopy "%BK_SOURCE%\snapshots" "%~dp0dist\_user_data_backup\snapshots" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 (
            echo [ERROR] Backup failed ^(snapshots^).
            goto :fail_pause
        )
    )
)



if exist build rmdir /s /q build

if exist "%~dp0dist\%DISTDIR%" rmdir /s /q "%~dp0dist\%DISTDIR%"



REM If this folder still exists, files were locked — exe remains and timestamps never update.

if exist "%~dp0dist\%DISTDIR%" (

    echo.

    echo [ERROR] dist\%DISTDIR% could NOT be deleted — CafeScraper.exe may still be RUNNING.

    echo          Close it ^(Task Manager^), then run build.bat again.

    echo          Folder that must be removable:

    echo          %CD%\dist\%DISTDIR%

    goto :fail_pause

)



if exist dist\CafeScraper.zip del /f /q dist\CafeScraper.zip

if exist CafeScraper_release.zip del /f /q CafeScraper_release.zip



echo [3/4] PyInstaller build...

echo.

REM --clean clears Analysis cache so outputs refresh reliably.

%PYINSTALLER_CMD% cafescraper.spec --noconfirm --clean



if errorlevel 1 (

    echo.

    echo [ERROR] PyInstaller failed — scroll up for Python traceback / ERROR lines.

    goto :fail_pause

)



if not exist "%~dp0dist\%DISTDIR%\CafeScraper.exe" (

    echo [ERROR] dist\%DISTDIR%\CafeScraper.exe missing after PyInstaller.

    goto :fail_pause

)



REM Semver for folder name still comes from repo root version.txt.
REM Do not copy version.txt next to the EXE (version is read from bundle _internal).

if exist "%~dp0dist\_user_data_backup\" (
    echo Restoring user state from dist\_user_data_backup into dist\%DISTDIR%\ ...

    set "RESTORE_ERR="

    if exist "%~dp0dist\_user_data_backup\data\" (
        if not exist "%~dp0dist\%DISTDIR%\data" mkdir "%~dp0dist\%DISTDIR%\data"
        robocopy "%~dp0dist\_user_data_backup\data" "%~dp0dist\%DISTDIR%\data" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 set "RESTORE_ERR=1"
    )

    if exist "%~dp0dist\_user_data_backup\crawler_config.json" (
        copy /y "%~dp0dist\_user_data_backup\crawler_config.json" "%~dp0dist\%DISTDIR%\" >nul
        if errorlevel 1 set "RESTORE_ERR=1"
    )

    if exist "%~dp0dist\_user_data_backup\comment_templates.json" (
        copy /y "%~dp0dist\_user_data_backup\comment_templates.json" "%~dp0dist\%DISTDIR%\" >nul
        if errorlevel 1 set "RESTORE_ERR=1"
    )

    if exist "%~dp0dist\_user_data_backup\sessions\" (
        if not exist "%~dp0dist\%DISTDIR%\sessions" mkdir "%~dp0dist\%DISTDIR%\sessions"
        robocopy "%~dp0dist\_user_data_backup\sessions" "%~dp0dist\%DISTDIR%\sessions" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 set "RESTORE_ERR=1"
    )

    if exist "%~dp0dist\_user_data_backup\snapshots\" (
        if not exist "%~dp0dist\%DISTDIR%\snapshots" mkdir "%~dp0dist\%DISTDIR%\snapshots"
        robocopy "%~dp0dist\_user_data_backup\snapshots" "%~dp0dist\%DISTDIR%\snapshots" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NJH /NJS
        if errorlevel 8 set "RESTORE_ERR=1"
    )

    if not defined RESTORE_ERR rmdir /s /q "%~dp0dist\_user_data_backup"
    if defined RESTORE_ERR echo [WARN] Restore had errors; keeping dist\_user_data_backup for manual recovery.
)



echo.

echo [4/4] Done (no ZIP — use scripts\pack_dist.ps1 when you distribute)

echo ============================================

echo   EXE folder:  dist\%DISTDIR%\

echo   Version:     repo version.txt ^(dist folder name only^); app reads bundle _internal

echo ============================================

echo.

echo Built artifact timestamps ^(should match just now^):

for %%I in ("dist\%DISTDIR%\CafeScraper.exe") do echo   CafeScraper.exe  %%~tI

for %%I in ("dist\%DISTDIR%\_internal") do echo   _internal folder   %%~tI

echo NOTE: cafescraper_launch.log updates when you RUN the exe, not when you build.

if exist "%~dp0dist\CafeScraper\CafeScraper.exe" (

    echo.

    echo [NOTE] Legacy dist\CafeScraper\ still exists ^(older builds^). Current EXE is under dist\%DISTDIR%\ — use that folder.

)



exit /b 0



:fail_pause

echo.

pause

exit /b 1

