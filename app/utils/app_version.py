# CafeScraper — semver source: repo root version.txt (see CHANGELOG.md)
from __future__ import annotations

import sys
from pathlib import Path

from app.utils.paths import get_project_root

_DEFAULT = "0.0.0"


def read_app_version() -> str:
    """프로젝트 루트 또는 번들 `_internal`/exe 옆의 `version.txt` 한 줄 semver."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "version.txt")
        candidates.append(Path(sys.executable).resolve().parent / "version.txt")
    else:
        candidates.append(get_project_root() / "version.txt")

    for p in candidates:
        try:
            if p.is_file():
                line = p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                if line:
                    return line
        except OSError:
            continue
    return _DEFAULT
