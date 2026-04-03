# -*- coding: utf-8 -*-
"""Repack col_setup into top 3 cards + full-width board + mode/save; keep col_main."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    start_pat = 'col_setup, col_main = st.columns([1, 2.2], gap="large")'
    end_pat = "\ndef _render_cafe_main_workspace():"
    if start_pat not in text:
        raise SystemExit("start pattern not found (already transformed?)")
    if end_pat not in text:
        raise SystemExit("end pattern not found")

    s = text.index(start_pat)
    e = text.index(end_pat)
    head = text[:s]
    tail = text[e:]
    mid_lines = text[s:e].splitlines(True)

    # Find line indices (0-based within mid_lines)
    def find_startswith(strip_prefix: str) -> int:
        for i, L in enumerate(mid_lines):
            if L.lstrip().startswith(strip_prefix):
                return i
        raise SystemExit(f"missing line: {strip_prefix!r}")

    i_setup_title = find_startswith('st.markdown("#### ⚙️ 수집 설정")')
    i_default = find_startswith("default_exclude = ")
    i_btn = find_startswith('if st.button("🔍 게시판 목록 가져오기"')
    i_sel = find_startswith("selected_urls_str = config.get")
    i_excl = find_startswith('with st.expander("🚫 수집대상 제외')
    i_mode = find_startswith('st.subheader("🔧 작업 모드")')
    i_db = None
    for i, L in enumerate(mid_lines):
        if L.startswith("    with st.container(border=True):") and i > i_mode:
            nxt = mid_lines[i + 1] if i + 1 < len(mid_lines) else ""
            if 'st.markdown("#### 💾 데이터/DB")' in nxt:
                i_db = i
                break
    if i_db is None:
        raise SystemExit("DB container not found")

    # i_btn_end: line after last line of button handler (search backward from i_sel)
    i_btn_end = i_sel  # exclusive: lines i_btn:i_btn_end are button block

    head_cafe = mid_lines[i_setup_title + 1 : i_default]
    init_block = mid_lines[i_default:i_btn]
    btn_block = mid_lines[i_btn:i_sel]
    board_block = mid_lines[i_sel:i_excl]
    filter_block = mid_lines[i_excl:i_mode]
    mode_block = mid_lines[i_mode:i_db]
    db_block = mid_lines[i_db:]

    def dedent_lines(lines: list[str], n: int) -> list[str]:
        out = []
        for L in lines:
            if L.strip() == "":
                out.append(L)
                continue
            c = 0
            while c < len(L) and L[c] == " " and c < n:
                c += 1
            # remove min(c, n) actually remove n leading spaces if present
            if L.startswith(" " * n):
                out.append(L[n:])
            else:
                out.append(L)
        return out

    # Hoist init (was 8 spaces) -> 0 spaces
    hoist = dedent_lines(init_block, 8)

    def indent_lines(lines: list[str], n: int) -> list[str]:
        p = " " * n
        return [p + L if L.strip() else L for L in lines]

    # Card1 body: head_cafe + btn_block, each line had 8 spaces; inside with _t1 / container need 8 spaces total — same as now
    card1_body = head_cafe + btn_block

    # Card2: filter + dates part only (filter_block includes exclude, admin, subheader dates, col1 col2, end_date)
    # filter_block ends before mode; already correct chunk i_excl:i_mode

    out: list[str] = []
    out.append(
        "# 상단 3카드(설정) + 하단 전폭(게시판·모드·저장) → 실행/리스트는 col_main\n"
    )
    out.extend(hoist)
    out.append('st.markdown("#### ⚙️ 수집 설정")\n')
    out.append('_t1, _t2, _t3 = st.columns([1, 1, 1], gap="medium")\n')
    out.append("with _t1:\n")
    out.append("    with st.container(border=True):\n")
    out.append('        st.caption("카페 · 연결")\n')
    out.extend(card1_body)  # already 8 spaces

    out.append("with _t2:\n")
    out.append("    with st.container(border=True):\n")
    out.append('        st.caption("필터 · 수집 기간")\n')
    out.extend(indent_lines(dedent_lines(filter_block, 8), 8))

    out.append("with _t3:\n")
    out.extend(indent_lines(dedent_lines(db_block, 4), 4))

    out.append("with st.container(border=True):\n")
    out.append('    st.markdown("##### 📋 게시판 선택 · 수집 대상")\n')
    out.extend(indent_lines(dedent_lines(board_block, 8), 4))

    out.append("with st.container(border=True):\n")
    out.append('    st.markdown("##### 🔧 작업 모드 · 저장")\n')
    out.extend(indent_lines(dedent_lines(mode_block, 8), 4))

    out.append("\ncol_main = st.container()\n")

    new_text = head + "".join(out) + tail
    APP.write_text(new_text, encoding="utf-8")
    print("OK:", APP)


if __name__ == "__main__":
    main()
