# -*- coding: utf-8 -*-
"""Move board picker under col1, work mode under col2 in app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def add_indent(body: str, spaces: int) -> str:
    p = " " * spaces
    out = []
    for line in body.splitlines(True):
        if line.strip():
            out.append(p + line)
        else:
            out.append(line)
    return "".join(out)


def main() -> None:
    text = APP.read_text(encoding="utf-8")

    board_hdr = 'with st.container(border=True):\n    st.markdown("##### 📋 게시판 선택'
    board_tail = "    board_url = selected_urls_str\n"
    mode_hdr = 'with st.container(border=True):\n    st.markdown("##### 🔧 작업 모드'
    mode_tail = '        st.success("✅ 설정이 저장되었습니다.")\n'

    i0 = text.index(board_hdr)
    i1 = text.index(board_tail, i0) + len(board_tail)
    board_full = text[i0:i1]
    blines = board_full.splitlines(True)
    if not blines[0].startswith("with st.container"):
        raise SystemExit("board: expected with st.container")
    body_board = "".join(blines[1:])
    body_board_ind = add_indent(body_board, 4)

    i_mode = text.index(mode_hdr, i1)
    i_mode_end = text.index(mode_tail, i_mode) + len(mode_tail)
    mode_full = text[i_mode:i_mode_end]
    mlines = mode_full.splitlines(True)
    if not mlines[0].startswith("with st.container"):
        raise SystemExit("mode: expected with st.container")
    body_mode = "".join(mlines[1:])
    body_mode_ind = add_indent(body_mode, 4)

    ins1_old = '''                except Exception as e:
                    st.error(f"오류: {e}")

with _t2:'''
    ins1_new = '''                except Exception as e:
                    st.error(f"오류: {e}")

    with st.container(border=True):
''' + body_board_ind + '''with _t2:'''
    if ins1_old not in text:
        raise SystemExit("insert point 1 not found")
    text = text.replace(ins1_old, ins1_new, 1)

    ins2_old = '''        start_date = col1.date_input("시작일", default_start)
        end_date = col2.date_input("종료일", default_end)


with _t3:'''
    ins2_new = '''        start_date = col1.date_input("시작일", default_start)
        end_date = col2.date_input("종료일", default_end)

    with st.container(border=True):
''' + body_mode_ind + '''with _t3:'''
    if ins2_old not in text:
        raise SystemExit("insert point 2 not found")
    text = text.replace(ins2_old, ins2_new, 1)

    # Remove remaining full-width board+mode (only place: right after DB 카드, unindented `with`)
    rm_anchor = 'st.error(f"복사/전환 실패: {e}")\nwith st.container(border=True):\n    st.markdown("##### 📋 게시판 선택'
    rm0 = text.index(rm_anchor) + len('st.error(f"복사/전환 실패: {e}")\n')
    rm1 = text.index(mode_tail, rm0) + len(mode_tail)
    while rm1 < len(text) and text[rm1] == "\n":
        rm1 += 1
    text = text[:rm0] + text[rm1:]

    APP.write_text(text, encoding="utf-8")
    print("OK:", APP)


if __name__ == "__main__":
    main()
