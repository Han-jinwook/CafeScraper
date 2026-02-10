import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import time
import random
import json

from crawler import NaverCafeCrawler
from app.utils.paths import get_config_path, resolve_event_db_path, get_project_root
from app.utils.event_db import init_event_db, save_event_comments, get_event_comments_count


st.set_page_config(page_title="이벤트 댓글 수집", layout="wide")

CONFIG_PATH = str(get_config_path())


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


config = load_config()
EVENT_DB_PATH = str(resolve_event_db_path(config.get("event_db_path")))
init_event_db(EVENT_DB_PATH)


if "event_crawler" not in st.session_state:
    st.session_state.event_crawler = None
if "event_logs" not in st.session_state:
    st.session_state.event_logs = []


log_placeholder = st.empty()


def update_logs(msg: str | None = None):
    if msg:
        ts = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_logs.append(f"[{ts}] {msg}")
    try:
        log_placeholder.markdown("### 📋 실시간 로그")
        recent = "\n\n".join(reversed(st.session_state.event_logs[-40:]))
        log_placeholder.text_area("", recent, height=280, label_visibility="collapsed", disabled=True)
    except:
        pass


st.title("🎫 카페 이벤트용 댓글 수집기")
st.caption("기간 내 게시글(모든 글)을 대상으로 댓글 작성자/날짜/내용을 별도 DB에 저장합니다.")


with st.sidebar:
    st.header("⚙️ 설정")

    cafe_url = st.text_input("카페 URL", value=config.get("event_cafe_url", "https://cafe.naver.com/sundreamd"))
    board_url = st.text_input(
        "대상 URL (전체글보기 권장)",
        value=config.get("event_board_url", "https://cafe.naver.com/f-e/cafes/27870803/menus/0"),
    )

    st.subheader("🚫 제외 게시판")
    default_exclude_boards = "\n".join(
        [
            "공지&이벤트",
            "자유 게시판",
            "먹거리 / 맛집",
            "멘토단 전용 (중상급자)",
            "음악 웃음 힐링",
            "제품사은품후기",
            "진급축하 / 진급문의",
            "회원상품 홍보",
            "(조사기)중고 직거래",
            "썬드림 앱's",
        ]
    )
    exclude_boards_text = st.text_area(
        "줄바꿈으로 구분 (해당 게시판 글은 목록 단계에서 제외)",
        value=config.get("event_exclude_boards", default_exclude_boards),
        height=120,
    )

    st.subheader("📅 기간 (게시글 작성일 기준)")
    default_start = datetime.now() - timedelta(days=7)
    if config.get("event_start_date"):
        try:
            default_start = datetime.strptime(config["event_start_date"], "%Y-%m-%d")
        except:
            pass
    default_end = datetime.now()
    if config.get("event_end_date"):
        try:
            default_end = datetime.strptime(config["event_end_date"], "%Y-%m-%d")
        except:
            pass

    c1, c2 = st.columns(2)
    start_date = c1.date_input("시작일", default_start)
    end_date = c2.date_input("종료일", default_end)

    st.subheader("⏱️ 딜레이(게시글 단위)")
    delay_min = st.number_input("최소(초)", min_value=0.0, max_value=20.0, value=float(config.get("event_delay_min", 2.0)), step=0.5)
    delay_max = st.number_input("최대(초)", min_value=0.0, max_value=30.0, value=float(config.get("event_delay_max", 4.0)), step=0.5)
    max_posts = st.number_input("최대 게시글(0=무제한)", min_value=0, max_value=200000, value=int(config.get("event_max_posts", 0)), step=100)

    st.subheader("🚫 제외 닉네임")
    exclude_nicks_text = st.text_area(
        "줄바꿈으로 구분 (해당 닉네임 댓글은 저장/집계에서 제외)",
        value=config.get("event_exclude_nicks", "마법사멀린\n해나라"),
        height=80,
    )

    st.subheader("💾 이벤트 DB 경로")
    event_db_path_text = st.text_input(
        "DB 절대경로(선택)",
        value=str(config.get("event_db_path", "")),
        placeholder=r"D:\CafeBreaker\data\event_comments.db",
    )
    st.caption("우선순위: 환경변수 `CAFESCRAPER_EVENT_DB_PATH` > 여기 입력 > 기본값(event_comments.db)")
    st.caption(f"현재 사용 DB: `{os.path.abspath(EVENT_DB_PATH)}`")
    st.metric("저장된 이벤트 댓글 수", f"{get_event_comments_count(EVENT_DB_PATH):,}개")

    if st.button("💾 설정 저장", width="stretch"):
        config["event_cafe_url"] = cafe_url
        config["event_board_url"] = board_url
        config["event_exclude_boards"] = exclude_boards_text
        config["event_start_date"] = start_date.strftime("%Y-%m-%d")
        config["event_end_date"] = end_date.strftime("%Y-%m-%d")
        config["event_delay_min"] = float(delay_min)
        config["event_delay_max"] = float(delay_max)
        config["event_max_posts"] = int(max_posts)
        config["event_exclude_nicks"] = exclude_nicks_text
        config["event_db_path"] = event_db_path_text.strip()
        save_config(config)
        st.success("✅ 저장 완료 (DB 경로를 바꿨다면 자동 반영됩니다)")
        st.rerun()


col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("1단계: 브라우저 열기", width="stretch"):
        if not st.session_state.event_crawler:
            st.session_state.event_crawler = NaverCafeCrawler("", debug_mode=False)
            st.session_state.event_crawler.set_status_callback(update_logs)
        st.session_state.event_crawler.start_browser()
        update_logs("✅ 브라우저가 열렸습니다. 로그인 후 2단계를 진행하세요.")
with col2:
    if st.button("2단계: 댓글 수집 시작", type="primary", width="stretch"):
        if not st.session_state.event_crawler or not st.session_state.event_crawler.driver:
            st.error("먼저 브라우저를 열어주세요.")
        else:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())

            update_logs("🔍 기간 내 게시글 목록 수집 시작...")
            # 게시글 리스트 수집(기간 필터는 기존 로직 사용)
            exclude_boards = [x.strip() for x in (exclude_boards_text or "").splitlines() if x.strip()]
            articles = st.session_state.event_crawler.scrape_board_list(board_url, start_dt, end_dt, exclude_boards=exclude_boards)
            if not articles:
                update_logs("⚠️ 기간 내 게시글을 찾지 못했습니다. URL/기간을 확인하세요.")
            else:
                if int(max_posts) > 0:
                    articles = articles[: int(max_posts)]

                update_logs(f"✅ 대상 게시글 {len(articles):,}개 확보. 댓글 수집 시작...")
                prog = st.progress(0.0)
                inserted_total = 0
                comments_seen_total = 0
                excluded_total = 0

                exclude_set = {x.strip().lower() for x in (exclude_nicks_text or "").splitlines() if x.strip()}

                for i, art in enumerate(articles):
                    prog.progress((i + 1) / len(articles))
                    title = (art.get("title") or "")[:30]
                    update_logs(f"💬 ({i+1}/{len(articles)}) '{title}...' 댓글 조회 중")

                    comments = st.session_state.event_crawler.get_all_comments_for_article(art.get("url") or "")
                    comments_seen_total += len(comments)

                    # 제외 닉네임 필터(저장/집계에서 제외)
                    filtered = []
                    for c in comments:
                        nn = str(c.get("nickname") or "").strip()
                        if nn and nn.lower() in exclude_set:
                            excluded_total += 1
                            continue
                        filtered.append(c)

                    ins = save_event_comments(EVENT_DB_PATH, art, filtered)
                    inserted_total += ins

                    update_logs(
                        f"✅ 댓글 {len(comments):,}개 조회 / 제외 {len(comments)-len(filtered):,}개 / 신규 저장 {ins:,}개 (누적 신규 {inserted_total:,})"
                    )

                    dmin = float(delay_min)
                    dmax = float(delay_max)
                    if dmax < dmin:
                        dmin, dmax = dmax, dmin
                    time.sleep(random.uniform(dmin, dmax))

                update_logs(
                    f"🎉 완료: 게시글 {len(articles):,}개 처리, 댓글 조회 {comments_seen_total:,}개, "
                    f"제외 {excluded_total:,}개, 신규 저장 {inserted_total:,}개"
                )
with col3:
    st.caption("페이지 목록이 안 보이면 Streamlit 재시작이 필요할 수 있습니다.")


update_logs()

st.markdown("---")
st.header("📊 저장된 이벤트 댓글")

show_limit = st.selectbox("표시 건수", options=[500, 2000, 10000, "전체"], index=0)
limit_sql = None if show_limit == "전체" else int(show_limit)

try:
    # 상단 집계(항상 DB 전체 기준) + 설정 기간 표시
    conn_stats = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    stats_row = pd.read_sql_query(
        """
        SELECT
            COUNT(DISTINCT post_id) AS posts_cnt,
            COUNT(*) AS comments_cnt,
            COUNT(DISTINCT comment_writer_id) AS people_cnt,
            COALESCE(SUM(comment_length), 0) AS chars_cnt
        FROM event_comments
        """,
        conn_stats,
    ).iloc[0]
    conn_stats.close()

    st.caption(f"설정 기간: **{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}** (게시글 작성일 기준)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 게시글", f"{int(stats_row['posts_cnt']):,}개")
    m2.metric("총 댓글", f"{int(stats_row['comments_cnt']):,}개")
    m3.metric("총 몇명(작성자)", f"{int(stats_row['people_cnt']):,}명")
    m4.metric("총 댓글 글자수", f"{int(stats_row['chars_cnt']):,}자")

    conn = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    df = pd.read_sql_query(
        (
            """
            SELECT
                post_date,
                board_name,
                post_title,
                comment_level,
                comment_nickname,
                comment_date,
                comment_length,
                comment_content,
                post_url
            FROM event_comments
            ORDER BY id DESC
            """
            + (f"\nLIMIT {limit_sql}\n" if limit_sql else "")
        ),
        conn,
    )
    conn.close()

    if df.empty:
        st.info("아직 저장된 데이터가 없습니다.")
    else:
        st.write(f"표시: {len(df):,}개")
        # 선택 삭제를 위한 data_editor
        if "event_editor_refresh" not in st.session_state:
            st.session_state.event_editor_refresh = 0
        if "selected_event_ids" not in st.session_state:
            st.session_state.selected_event_ids = []

        df_display = df.copy()
        df_display.insert(0, "선택", False)

        # row 식별자(id) 필요: 현재 df에는 id가 없으므로 추가 조회로 id를 붙인다
        # 표시용 df는 정렬/필드가 고정되어 있으니, 동일 조건으로 id까지 가져온다.
        conn_id = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
        df_ids = pd.read_sql_query(
            (
                """
                SELECT
                    id,
                    post_date,
                    board_name,
                    post_title,
                    comment_level,
                    comment_nickname,
                    comment_date,
                    comment_length,
                    comment_content,
                    post_url
                FROM event_comments
                ORDER BY id DESC
                """
                + (f"\nLIMIT {limit_sql}\n" if limit_sql else "")
            ),
            conn_id,
        )
        conn_id.close()

        df_display = df_ids.copy()
        df_display.insert(0, "선택", False)

        # 이전 선택 복원
        for idx, rid in enumerate(df_display["id"].tolist()):
            if rid in st.session_state.selected_event_ids:
                df_display.at[idx, "선택"] = True

        edited = st.data_editor(
            df_display,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", default=False),
                "id": "row_id",
                "post_url": st.column_config.LinkColumn("원글 링크"),
            },
            hide_index=True,
            width="stretch",
            disabled=[c for c in df_display.columns if c != "선택"],
            key=f"event_editor_{st.session_state.event_editor_refresh}",
        )
        st.session_state.selected_event_ids = edited[edited["선택"] == True]["id"].tolist()

        # 삭제 버튼들
        st.markdown("---")
        a1, a2, a3 = st.columns([1, 1, 2])
        with a1:
            if st.button("☑️ 전체 선택", width="stretch", key="select_all_event_rows"):
                st.session_state.selected_event_ids = df_display["id"].tolist()
                st.session_state.event_editor_refresh += 1
                st.rerun()
        with a2:
            if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_event_rows"):
                st.session_state.selected_event_ids = []
                st.session_state.event_editor_refresh += 1
                st.rerun()
        with a3:
            if st.session_state.selected_event_ids:
                if st.button(
                    f"🗑️ 선택 삭제 ({len(st.session_state.selected_event_ids):,})",
                    type="primary",
                    width="stretch",
                    key="delete_selected_event_rows",
                ):
                    conn_del = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
                    cur = conn_del.cursor()
                    for rid in st.session_state.selected_event_ids:
                        cur.execute("DELETE FROM event_comments WHERE id = ?", (int(rid),))
                    conn_del.commit()
                    conn_del.close()
                    st.session_state.selected_event_ids = []
                    st.session_state.event_editor_refresh += 1
                    st.success("✅ 선택 항목 삭제 완료")
                    st.rerun()
            else:
                st.button("🗑️ 선택 삭제", disabled=True, width="stretch", key="delete_selected_event_rows_disabled")

        # 전체 삭제(확인 2단계)
        st.markdown("---")
        if "confirm_delete_all" not in st.session_state:
            st.session_state.confirm_delete_all = False

        b1, b2 = st.columns([1, 3])
        with b1:
            if not st.session_state.confirm_delete_all:
                if st.button("🧨 전체 삭제", width="stretch", key="arm_delete_all"):
                    st.session_state.confirm_delete_all = True
                    st.warning("⚠️ 전체 삭제를 누르셨습니다. 오른쪽 버튼으로 최종 확인하세요.")
            else:
                if st.button("✅ 전체 삭제 취소", width="stretch", key="cancel_delete_all"):
                    st.session_state.confirm_delete_all = False
        with b2:
            if st.session_state.confirm_delete_all:
                if st.button("🧨 정말로 전체 삭제(복구 불가)", type="primary", width="stretch", key="confirm_delete_all"):
                    conn_all = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
                    cur = conn_all.cursor()
                    cur.execute("DELETE FROM event_comments")
                    conn_all.commit()
                    conn_all.close()
                    st.session_state.confirm_delete_all = False
                    st.session_state.selected_event_ids = []
                    st.session_state.event_editor_refresh += 1
                    st.success("✅ 전체 삭제 완료")
                    st.rerun()

        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ CSV 다운로드(현재 표시분)",
            data=csv_bytes,
            file_name=f"event_comments_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch",
        )

        # 전체 CSV 다운로드
        if st.button("⬇️ CSV 다운로드(전체)", width="stretch"):
            conn2 = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
            df_all = pd.read_sql_query(
                """
                SELECT
                    post_date,
                    board_name,
                    post_title,
                    comment_level,
                    comment_nickname,
                    comment_date,
                    comment_length,
                    comment_content,
                    post_url
                FROM event_comments
                ORDER BY id DESC
                """,
                conn2,
            )
            conn2.close()
            all_bytes = df_all.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "⬇️ 전체 CSV 파일 생성/다운로드",
                data=all_bytes,
                file_name=f"event_comments_ALL_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch",
                key="download_all_csv",
            )
except Exception as e:
    st.error(f"DB 조회 오류: {e}")

st.markdown("---")
st.header("📌 최종 결과물 (등급/별명/댓글 수/댓글 글자 수)")
try:
    conn3 = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    df_sum = pd.read_sql_query(
        """
        SELECT
            COALESCE(NULLIF(TRIM(comment_level), ''), 'unknown') AS level,
            COALESCE(NULLIF(TRIM(comment_nickname), ''), 'unknown') AS nickname,
            COUNT(*) AS comment_count,
            COALESCE(SUM(comment_length), 0) AS comment_chars
        FROM event_comments
        GROUP BY level, nickname
        ORDER BY comment_count DESC, comment_chars DESC
        """,
        conn3,
    )
    conn3.close()

    if df_sum.empty:
        st.info("아직 집계할 데이터가 없습니다.")
    else:
        st.dataframe(df_sum, width="stretch", hide_index=True)
        sum_bytes = df_sum.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ 집계 CSV 다운로드",
            data=sum_bytes,
            file_name=f"event_summary_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch",
        )
except Exception as e:
    st.error(f"집계 오류: {e}")

