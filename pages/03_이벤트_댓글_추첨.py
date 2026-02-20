import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import time
import random
import json

from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.paths import get_config_path, resolve_event_db_path, get_project_root
from app.utils.event_db import init_event_db, save_event_comments, get_event_comments_count


st.set_page_config(page_title="이벤트 댓글 수집", layout="wide")

# -----------------------------------------------------------------------------
# 🎨 UI/UX Design System (Custom CSS)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp {
        background-color: #f8f9fa;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    
    /* 카드 스타일 컨테이너 */
    .css-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
    }
    
    /* 헤더 스타일 */
    h1 {
        color: #111827;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    h2 {
        color: #374151;
        font-weight: 600 !important;
        font-size: 1.4rem !important;
        margin-top: 0 !important;
    }
    h3 {
        color: #4b5563;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    
    /* 메트릭 스타일 */
    div[data-testid="stMetric"] {
        background-color: #f3f4f6;
        padding: 16px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #6b7280;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        color: #1f2937;
        font-weight: 700;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        border-radius: 8px;
        height: 44px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background-color: #f9fafb;
        border-radius: 8px;
        font-weight: 600;
        color: #374151;
    }
    
    /* 구분선 */
    hr {
        margin: 2rem 0;
        border-color: #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)

# 메인 크롤링 구동 중에는 다른 메뉴 작업을 잠시 차단
if st.session_state.get("crawl_running", False):
    st.warning("⚠️ 메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

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


def update_logs(msg: str | None = None):
    if msg:
        ts = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_logs.append(f"[{ts}] {msg}")


# -----------------------------------------------------------------------------
# Header Section
# -----------------------------------------------------------------------------
st.title("🎫 이벤트 댓글 분석 스튜디오")
st.markdown("""
<div style='margin-bottom: 20px; color: #6b7280;'>
    특정 기간 내 게시글의 댓글을 수집하고, 중복 참여자 및 열성 회원을 분석하는 도구입니다.
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.header("⚙️ 환경 설정")
    st.caption("수집 대상 및 규칙을 설정합니다.")

    cafe_url = st.text_input("카페 URL", value=config.get("event_cafe_url", "https://cafe.naver.com/sundreamd"))
    board_url = st.text_input(
        "대상 게시판 URL",
        value=config.get("event_board_url", "https://cafe.naver.com/f-e/cafes/27870803/menus/0"),
        help="전체글보기 URL을 권장합니다."
    )

    with st.expander("🚫 제외 설정 (게시판/닉네임)"):
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
            "제외 게시판 (줄바꿈 구분)",
            value=config.get("event_exclude_boards", default_exclude_boards),
            height=120,
        )
        exclude_nicks_text = st.text_area(
            "제외 닉네임 (줄바꿈 구분)",
            value=config.get("event_exclude_nicks", "마법사멀린\n해나라"),
            height=80,
            help="운영자 등 집계에서 제외할 닉네임을 입력하세요."
        )

    st.subheader("📅 수집 기간")
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

    with st.expander("⏱️ 고급 속도 설정"):
        delay_min = st.number_input("최소 대기(초)", min_value=0.0, max_value=20.0, value=float(config.get("event_delay_min", 2.0)), step=0.5)
        delay_max = st.number_input("최대 대기(초)", min_value=0.0, max_value=30.0, value=float(config.get("event_delay_max", 4.0)), step=0.5)
        max_posts = st.number_input("최대 수집 글 수(0=무제한)", min_value=0, max_value=200000, value=int(config.get("event_max_posts", 0)), step=100)

    st.markdown("---")
    st.subheader("💾 데이터베이스")
    event_db_path_text = st.text_input(
        "DB 경로",
        value=str(config.get("event_db_path", "")),
        placeholder=r"D:\CafeBreaker\data\event_comments.db",
    )
    st.caption(f"현재 DB: `{os.path.basename(EVENT_DB_PATH)}`")
    
    if st.button("💾 설정 저장하기", width="stretch"):
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
        st.success("✅ 설정이 저장되었습니다.")
        time.sleep(1)
        st.rerun()


# -----------------------------------------------------------------------------
# Control Panel (Card UI)
# -----------------------------------------------------------------------------
st.markdown('<div class="css-card">', unsafe_allow_html=True)
st.markdown("### 🚀 수집 제어 센터")
c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([1, 1, 2])

with c_ctrl1:
    if st.button("1️⃣ 브라우저 열기", width="stretch"):
        if not st.session_state.event_crawler:
            st.session_state.event_crawler = NaverCafeCrawler("", debug_mode=False)
            st.session_state.event_crawler.set_status_callback(update_logs)
        st.session_state.event_crawler.start_browser()
        update_logs("✅ 브라우저가 열렸습니다. 로그인 후 2단계를 진행하세요.")

with c_ctrl2:
    if st.button("2️⃣ 댓글 수집 시작", type="primary", width="stretch"):
        if not st.session_state.event_crawler or not st.session_state.event_crawler.driver:
            st.error("먼저 브라우저를 열어주세요.")
        else:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())

            update_logs("🔍 기간 내 게시글 목록 수집 시작...")
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

with c_ctrl3:
    # 로그 영역 (간략화)
    if st.session_state.event_logs:
        last_log = st.session_state.event_logs[-1]
        st.info(f"📋 {last_log}")
    else:
        st.caption("대기 중...")

st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Dashboard (Card UI)
# -----------------------------------------------------------------------------
update_logs()

st.markdown('<div class="css-card">', unsafe_allow_html=True)
st.markdown("### 📊 데이터 대시보드")

show_limit = st.selectbox("표시 건수", options=[500, 2000, 10000, "전체"], index=0)
limit_sql = None if show_limit == "전체" else int(show_limit)

try:
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

    st.caption(f"📅 분석 기간: **{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}**")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 게시글", f"{int(stats_row['posts_cnt']):,}개")
    m2.metric("수집된 댓글", f"{int(stats_row['comments_cnt']):,}개")
    m3.metric("참여 인원", f"{int(stats_row['people_cnt']):,}명")
    m4.metric("총 글자수", f"{int(stats_row['chars_cnt']):,}자")

    st.divider()

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
        st.info("📭 아직 저장된 데이터가 없습니다. 수집을 시작해보세요.")
    else:
        # 데이터 에디터 및 삭제 로직
        if "event_editor_refresh" not in st.session_state:
            st.session_state.event_editor_refresh = 0
        if "selected_event_ids" not in st.session_state:
            st.session_state.selected_event_ids = []

        df_display = df.copy()
        df_display.insert(0, "선택", False)

        conn_id = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
        df_ids = pd.read_sql_query(
            (
                """
                SELECT id FROM event_comments ORDER BY id DESC
                """
                + (f"\nLIMIT {limit_sql}\n" if limit_sql else "")
            ),
            conn_id,
        )
        conn_id.close()
        
        # ID 매핑 (화면 표시용 DF와 ID DF의 행 수가 같아야 함)
        if len(df_ids) == len(df_display):
            df_display["id"] = df_ids["id"]
        else:
            # 혹시 모를 불일치 시 안전장치
            df_display["id"] = range(len(df_display))

        # 이전 선택 복원
        selected_set = set(st.session_state.selected_event_ids)
        df_display["선택"] = df_display["id"].apply(lambda x: x in selected_set)

        edited = st.data_editor(
            df_display.drop(columns=["id"]), # ID 컬럼은 숨김
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", default=False),
                "post_url": st.column_config.LinkColumn("원글 링크"),
                "comment_content": st.column_config.TextColumn("댓글 내용", width="large"),
            },
            hide_index=True,
            width="stretch",
            key=f"event_editor_{st.session_state.event_editor_refresh}",
        )
        
        # 선택된 ID 업데이트 (edited는 인덱스가 유지됨)
        # data_editor의 리턴값은 수정된 DF임.
        # 선택된 행의 인덱스를 찾아서 원본 ID를 매핑해야 함.
        # 간단하게: edited의 순서는 df_display와 같음.
        
        # 수정된 체크박스 상태 반영
        current_selection = []
        # edited는 사용자가 체크한 결과가 반영된 DF
        # 여기서 '선택'이 True인 행의 인덱스를 가져와서 df_display['id']와 매핑
        true_indices = edited.index[edited["선택"]].tolist()
        # df_display는 원본 DF에 id가 붙어있음.
        current_selection = df_display.loc[true_indices, "id"].tolist()
        
        st.session_state.selected_event_ids = current_selection

        # 하단 액션 버튼
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        a1, a2, a3, a4 = st.columns([1, 1, 1, 1])
        with a1:
            if st.button("☑️ 전체 선택", width="stretch", key="select_all"):
                st.session_state.selected_event_ids = df_display["id"].tolist()
                st.session_state.event_editor_refresh += 1
                st.rerun()
        with a2:
            if st.button("⬜ 전체 해제", width="stretch", key="deselect_all"):
                st.session_state.selected_event_ids = []
                st.session_state.event_editor_refresh += 1
                st.rerun()
        with a3:
            if st.session_state.selected_event_ids:
                if st.button(f"🗑️ 삭제 ({len(st.session_state.selected_event_ids)})", type="primary", width="stretch"):
                    conn_del = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
                    cur = conn_del.cursor()
                    for rid in st.session_state.selected_event_ids:
                        cur.execute("DELETE FROM event_comments WHERE id = ?", (int(rid),))
                    conn_del.commit()
                    conn_del.close()
                    st.session_state.selected_event_ids = []
                    st.session_state.event_editor_refresh += 1
                    st.success("삭제 완료")
                    st.rerun()
            else:
                st.button("🗑️ 삭제", disabled=True, width="stretch")
        
        with a4:
             # CSV 다운로드
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "⬇️ CSV 저장",
                data=csv_bytes,
                file_name=f"event_comments_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch",
            )

except Exception as e:
    st.error(f"DB 조회 오류: {e}")

st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Duplicate Analysis Section (Premium Feature Card)
# -----------------------------------------------------------------------------
st.markdown('<div class="css-card" style="background-color: #f0f9ff; border: 1px solid #bae6fd;">', unsafe_allow_html=True)
st.markdown("### 🕵️ 중복/복붙 댓글 정밀 분석")
st.caption("동일한 작성자가 똑같은 내용을 반복해서 작성한 경우를 찾아냅니다. (어뷰징 탐지)")

if st.button("🔍 중복 분석 실행", type="primary"):
    with st.spinner("댓글 데이터를 정밀 분석 중입니다..."):
        try:
            conn_an = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
            df_an = pd.read_sql_query("SELECT comment_nickname, comment_content, comment_length FROM event_comments", conn_an)
            conn_an.close()

            if df_an.empty:
                st.warning("분석할 데이터가 없습니다.")
            else:
                dup_check = df_an.groupby(['comment_nickname', 'comment_content']).size().reset_index(name='count')
                dups_only = dup_check[dup_check['count'] > 1].copy()
                
                if dups_only.empty:
                    st.success("✅ 클린! 중복/복붙 댓글이 발견되지 않았습니다.")
                else:
                    total_dup_count = dups_only['count'].sum()
                    total_dup_groups = len(dups_only)
                    redundant_count = total_dup_count - total_dup_groups
                    dups_only['len'] = dups_only['comment_content'].apply(lambda x: len(str(x)))
                    redundant_chars = (dups_only['len'] * (dups_only['count'] - 1)).sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("총 중복 댓글 수", f"{total_dup_count:,}개", delta="어뷰징 의심", delta_color="inverse")
                    m2.metric("중복 패턴 수", f"{total_dup_groups:,}개")
                    m3.metric("잉여 글자수", f"{redundant_chars:,}자")
                    
                    st.divider()
                    st.markdown("#### 📋 중복 작성자 상세 리포트")
                    
                    spammers = dups_only.groupby('comment_nickname')
                    spammer_list = []
                    for nick, group in spammers:
                        total_c = group['count'].sum()
                        spammer_list.append((nick, total_c, group))
                    
                    spammer_list.sort(key=lambda x: x[1], reverse=True)
                    
                    for nick, count, group in spammer_list:
                        with st.expander(f"👤 {nick} (총 {count}개 중복 발견)"):
                            display_df = group[['comment_content', 'count']].copy()
                            display_df.columns = ['중복 내용', '반복 횟수']
                            display_df = display_df.sort_values('반복 횟수', ascending=False)
                            st.table(display_df)

        except Exception as e:
            st.error(f"분석 중 오류 발생: {e}")

st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Summary Section
# -----------------------------------------------------------------------------
st.markdown('<div class="css-card">', unsafe_allow_html=True)
st.markdown("### 📌 최종 집계 (참여자 랭킹)")
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
        st.dataframe(
            df_sum, 
            width=None, 
            hide_index=True,
            column_config={
                "level": "등급",
                "nickname": "닉네임",
                "comment_count": st.column_config.NumberColumn("댓글 수", format="%d개"),
                "comment_chars": st.column_config.NumberColumn("총 글자수", format="%d자"),
            }
        )
        
        sum_bytes = df_sum.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ 랭킹 리포트 다운로드",
            data=sum_bytes,
            file_name=f"event_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch",
        )
except Exception as e:
    st.error(f"집계 오류: {e}")

st.markdown('</div>', unsafe_allow_html=True)
