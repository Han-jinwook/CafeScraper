# -*- coding: utf-8 -*-
"""Remove col_setup/col_main split: settings dedent to top-level; col_main body dedented."""
from __future__ import annotations

import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"
COMMENT = (
    "# 레이아웃: 상단 전폭 = 수집·DB 설정 / 하단 전폭 = 실행·진행·리스트 (페이지 메뉴는 사이드바)\n"
)


def dedent(line: str, n: int = 4) -> str:
    if not line.strip():
        return line
    i = 0
    while i < len(line) and line[i] == " ":
        i += 1
    if i >= n:
        return line[n:]
    return line


def main() -> None:
    lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)
    new: list[str] = []
    i = 0
    while i < len(lines):
        L = lines[i]
        if L.startswith("col_setup, col_main = st.columns"):
            new.append(COMMENT)
            i += 1
            continue
        if L.startswith("with col_setup:"):
            i += 1
            while i < len(lines) and not lines[i].startswith("def _render_cafe_main_workspace():"):
                new.append(dedent(lines[i]))
                i += 1
            continue
        if L.startswith("with col_main:"):
            i += 1
            while i < len(lines):
                new.append(dedent(lines[i]))
                i += 1
            break
        new.append(L)
        i += 1
    APP.write_text("".join(new), encoding="utf-8")
    print("OK")


if __name__ == "__main__":
    main()
