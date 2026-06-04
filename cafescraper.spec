# -*- mode: python ; coding: utf-8 -*-
# CafeScraper — bump version.txt + CHANGELOG when changing deps/datas.
"""PyInstaller spec: run_app.py → dist/cafescraper_V{semver}/ (semver from version.txt).
Requires: run from project root: pyinstaller cafescraper.spec --noconfirm
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_ROOT = os.path.dirname(os.path.abspath(SPECPATH))
if not os.path.isfile(os.path.join(SPEC_ROOT, 'run_app.py')):
    SPEC_ROOT = os.path.abspath(os.getcwd())


def _collect_folder_name(root: str) -> str:
    """ZIP 규칙(cafescraper_Vx.y.z)과 동일 접두로 dist 폴더명을 정한다."""
    p = os.path.join(root, 'version.txt')
    sem_safe = ''
    try:
        with open(p, 'r', encoding='utf-8') as f:
            raw = (f.readline() or '').strip().lstrip('v')
        sem_safe = ''.join(c for c in raw if (c.isalnum() or c in '._-'))
    except OSError:
        pass
    if not sem_safe:
        sem_safe = '0.0.0'
    return f'cafescraper_V{sem_safe}'


COLLECT_FOLDER = _collect_folder_name(SPEC_ROOT)

RUN_APP = os.path.join(SPEC_ROOT, 'run_app.py')
RT_HOOK = os.path.join(SPEC_ROOT, 'runtime_hook_streamlit.py')

datas = []
binaries = []
hiddenimports = []

for pkg in ('streamlit', 'altair', 'pyarrow', 'pandas'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

# selenium + undetected-chromedriver pull many deps via hooks; collect selenium data/binaries minimally
_tmp = collect_all('selenium')
datas += _tmp[0]
binaries += _tmp[1]
hiddenimports += _tmp[2]

for pkg in ('PIL', 'lxml', 'bs4', 'pyperclip'):
    try:
        _tmp = collect_all(pkg)
        datas += _tmp[0]
        binaries += _tmp[1]
        hiddenimports += _tmp[2]
    except Exception:
        pass

from PyInstaller.utils.hooks import copy_metadata
datas += copy_metadata('streamlit')


# App layout at bundle root (_MEIPASS): app.py, pages/, app/, .streamlit/, …
datas += [
    (os.path.join(SPEC_ROOT, 'app.py'), '.'),
    (os.path.join(SPEC_ROOT, 'pages'), 'pages'),
    (os.path.join(SPEC_ROOT, 'app'), 'app'),
    (os.path.join(SPEC_ROOT, '.streamlit'), '.streamlit'),
]
_ct = os.path.join(SPEC_ROOT, 'comment_templates.json')
if os.path.isfile(_ct):
    datas.append((_ct, '.'))
_ver = os.path.join(SPEC_ROOT, 'version.txt')
if os.path.isfile(_ver):
    datas.append((_ver, '.'))

hiddenimports += collect_submodules("webview")

hiddenimports += [
    'undetected_chromedriver',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
]

a = Analysis(
    [RUN_APP],
    pathex=[SPEC_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[RT_HOOK],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CafeScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=COLLECT_FOLDER,
)
