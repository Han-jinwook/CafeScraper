# -*- coding: utf-8 -*-
"""One-shot: Stitch-like 2-column main layout (settings+DB | workspace). Run from repo root."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

STEP2_FN = '''
def _is_step2_ready() -> bool:
    if bool(st.session_state.get("login_confirmed", False)):
        return True
    crawler = st.session_state.get("crawler")
    if not crawler or not getattr(crawler, "driver", None):
        return False
    try:
        cookies = crawler.driver.get_cookies() or []
        cookie_names = {str(c.get("name", "")).upper() for c in cookies}
        return ("NID_SES" in cookie_names) or ("NID_AUT" in cookie_names)
    except:
        return False


'''

GUIDE_MD = '''            **1. 기본 수집(단일 모드)**
            - 설정된 기간의 게시글을 수집합니다.
            - 새로운 글은 추가하고, 이미 수집된 글 중 **등급이 비어있는 경우 자동으로 채웁니다.**
            - 별도 복구 모드를 고르지 않아도 스마트 보강이 함께 동작합니다.

            **2. 수집 체감 속도 안내 (자동 적용)**
            - **50개씩 보기**: 크롤러가 자동으로 게시판 목록을 '50개씩 보기'로 전환하여 탐색 속도를 높입니다.
            - **종료일 기준 자동 시작페이지(권장)**: 종료일에 맞는 페이지를 자동으로 찾아 점프합니다. 수동 지정보다 안정적입니다.
            - **수동 시작 페이지(선택)**: 체크 해제 시 이전 실행 로그의 마지막 페이지를 기준으로 직접 지정할 수 있습니다.
            - **체감 소요시간**: 일반적으로 1건당 약 15~20초 내외가 걸릴 수 있습니다.
            - **소요시간 변동 요인**: 네트워크 품질, 네이버 페이지 로딩 속도, 게시글 본문 길이, 댓글 수, 이미지/동적요소 렌더링 상태, 차단 회피용 휴식 타이밍에 따라 더 길어질 수 있습니다.

            **3. 안전 장치 (자동 적용)**
            - **연속 실패 자동 중단**: 40회 이상 연속으로 수집에 실패하면 작업이 자동 중단되고 체크포인트가 저장됩니다.
            - **중복 방지**: 이미 수집된 글은 건너뛰며, 필요한 경우에만 업데이트합니다.
            '''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # 1) Remove early logo block (moved into col_main)
    start = None
    end = None
    for i, L in enumerate(lines):
        if L.startswith("# UI 구성: 로고"):
            start = i
        if start is not None and L.strip() == ")" and i > start + 5:
            # closing of st.markdown in expander
            prev = "".join(x.strip() for x in lines[i - 3 : i])
            if "중복 방지" in prev:
                end = i + 1
                break
    if start is None or end is None:
        raise SystemExit("Could not find logo block to remove")
    del lines[start:end]

    # 2) Insert _is_step2_ready after _is_browser_opened()
    insert_at = None
    for i, L in enumerate(lines):
        if L.startswith("def _is_browser_opened()"):
            for j in range(i, min(i + 20, len(lines))):
                if lines[j].strip() == "return False" and j > i + 3:
                    # second return False is inside except — need blank line after function
                    pass
            break
    for i, L in enumerate(lines):
        if L.startswith("def _is_overall_board_url"):
            insert_at = i
            break
    if insert_at is None:
        raise SystemExit("Could not find _is_overall_board_url")
    if any("def _is_step2_ready" in L for L in lines[: insert_at + 5]):
        pass  # already patched
    else:
        lines.insert(insert_at, STEP2_FN)

    # Re-find with st.sidebar after possible line shifts
    idx_sidebar = None
    for i, L in enumerate(lines):
        if L.startswith("with st.sidebar:"):
            idx_sidebar = i
            break
    if idx_sidebar is None:
        raise SystemExit("with st.sidebar not found")

    idx_main = None
    for i, L in enumerate(lines):
        if L.startswith("# 메인 화면"):
            idx_main = i
            break
    if idx_main is None:
        raise SystemExit("# 메인 화면 not found")

    # Sidebar inner: between 'with st.sidebar:' and '# 메인 화면'
    inner = lines[idx_sidebar + 1 : idx_main]
    if not inner:
        raise SystemExit("empty sidebar inner")

    split_i = None
    for i in range(len(inner) - 1):
        if inner[i].strip() == 'st.markdown("---")' and 'st.header("💾 데이터/DB")' in inner[i + 1]:
            split_i = i
            break
    if split_i is None:
        raise SystemExit("Could not split settings / DB sections")

    part1 = inner[:split_i]
    part2 = inner[split_i + 2 :]

    if not part1[0].lstrip().startswith('st.header("⚙️ 수집 설정")'):
        raise SystemExit(f"Unexpected first sidebar line: {part1[0]!r}")

    def bump(s: str) -> str:
        if not s.strip():
            return s
        return "    " + s

    part1_new = ['        st.markdown("#### ⚙️ 수집 설정")\n'] + [bump(x) for x in part1[1:]]
    part2_new = ['        st.markdown("#### 💾 데이터/DB")\n'] + [bump(x) for x in part2]

    layout = (
        "# 시안 레이아웃: 좌 설정+DB 카드 / 우 실행 영역 (페이지 메뉴는 왼쪽 사이드바)\n"
        "with st.sidebar:\n"
        '    st.markdown("##### **CafeMonster**")\n'
        '    st.caption("카페 추출기 Pro · 페이지 이동 ↓")\n'
        "\n"
        "col_setup, col_main = st.columns([1, 2.2], gap=\"large\")\n"
        "\n"
        "with col_setup:\n"
        "    with st.container(border=True):\n"
        + "".join(part1_new)
        + "    with st.container(border=True):\n"
        + "".join(part2_new)
    )

    main_tail = lines[idx_main + 1 :]
    # Drop duplicate _is_step2_ready block in tail
    out_tail: list[str] = []
    i = 0
    while i < len(main_tail):
        L = main_tail[i]
        if L.startswith("# 2단계 활성화 조건"):
            i += 1
            continue
        if L.startswith("def _is_step2_ready"):
            i += 1
            while i < len(main_tail) and main_tail[i].strip() != "":
                i += 1
            if i < len(main_tail) and main_tail[i].strip() == "":
                i += 1
            continue
        out_tail.append(L)
        i += 1

    def indent_body(body: list[str], spaces: str) -> str:
        out = []
        for L in body:
            if L.strip():
                out.append(spaces + L)
            else:
                out.append(L)
        return "".join(out)

    render_fn = (
        "def _render_cafe_main_workspace():\n"
        + indent_body(out_tail, "    ")
        + "\n"
    )

    col_main_block = (
        "\n"
        "with col_main:\n"
        "    st.markdown(\n"
        '        """\n'
        "        <div style=\\\"display:flex;align-items:center;justify-content:space-between;"
        "padding:0.25rem 0 1rem 0;border-bottom:1px solid rgba(192,201,195,0.35);margin-bottom:0.5rem;\\\">"
        "<span style=\\\"font-family:Manrope,Inter,sans-serif;font-weight:800;color:#003629;font-size:0.95rem;\\\">"
        "Crawler Control Center</span>"
        "<span style=\\\"font-size:0.78rem;color:#4c616c;\\\">Dashboard</span></div>\n"
        '        """,\n'
        "        unsafe_allow_html=True,\n"
        "    )\n"
        "    _logo_path = Path(__file__).resolve().parent / \"assets\" / \"CafeMonster_logo.png\"\n"
        "    _hdr_logo, _hdr_text = st.columns([1, 3.2])\n"
        "    with _hdr_logo:\n"
        "        if _logo_path.exists():\n"
        "            st.image(str(_logo_path), use_container_width=True)\n"
        "    with _hdr_text:\n"
        "        st.markdown(f\"## [{DISPLAY_CAFE_NAME}] 카페 추출기 Pro V1.0\")\n"
        '        st.caption("안전 우선 수집 워크플로우 · 설정 저장 → 브라우저 열기 → 크롤링 시작")\n'
        '        with st.expander("📖 사용 가이드 (필독)", expanded=False):\n'
        "            st.markdown(\n"
        f'                """\n{GUIDE_MD}                """\n'
        "            )\n"
        "    with st.container(border=True):\n"
        "        _render_cafe_main_workspace()\n"
    )

    head = lines[:idx_sidebar]
    new_text = "".join(head) + layout + render_fn + col_main_block

    APP.write_text(new_text, encoding="utf-8")
    print("OK:", APP)


if __name__ == "__main__":
    main()
