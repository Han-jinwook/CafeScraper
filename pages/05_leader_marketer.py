import streamlit as st
import pandas as pd
import os
import time
import random
import json
import re
import traceback
import html
import uuid
import threading
from datetime import datetime
from pathlib import Path

from selenium.webdriver.common.by import By

from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.paths import get_config_path
from app.utils.streamlit_top_nav import (
    render_main_top_nav,
    render_settings_card_title,
    inject_settings_three_cards_css,
)

st.set_page_config(
    page_title="운영진 마케터 - CafeScraper",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 1. 탑 네비게이션 가동
render_main_top_nav(active="marketer")

CONFIG_PATH = str(get_config_path())

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)

config = load_config()

# 2. 세션 상태 정의
if "marketer_logs" not in st.session_state:
    st.session_state.marketer_logs = []
if "marketer_leaders" not in st.session_state:
    st.session_state.marketer_leaders = []
if "marketer_running" not in st.session_state:
    st.session_state.marketer_running = False
if "marketer_stop_requested" not in st.session_state:
    st.session_state.marketer_stop_requested = False
if "marketer_thread" not in st.session_state:
    st.session_state.marketer_thread = None

# 발송 진행률 상태
if "marketer_send_progress" not in st.session_state:
    st.session_state.marketer_send_progress = 0.0
if "marketer_send_status_text" not in st.session_state:
    st.session_state.marketer_send_status_text = ""

# 3. 사용자 다운로드 폴더 경로 구하기 (윈도우 표준 규정 준수)
def get_user_download_dir() -> Path:
    home = Path.home()
    try:
        import winreg
        sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            downloads_dir, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            if downloads_dir and os.path.exists(downloads_dir):
                return Path(downloads_dir)
    except Exception:
        pass
    downloads = home / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads

def log_message(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.marketer_logs.append(f"[{timestamp}] {msg}")

# 4. 백그라운드 작업 스레드 함수
def run_extraction_job(cafe_url_or_name: str):
    st.session_state.marketer_running = True
    st.session_state.marketer_stop_requested = False
    
    crawler = None
    try:
        log_message("🌐 undetected-chromedriver 브라우저 실행 중...")
        crawler = NaverCafeCrawler(debug_mode=True)
        # 로그 콜백 연결
        def crawler_log_callback(msg):
            log_message(msg)
        crawler.set_status_callback(crawler_log_callback)
        
        crawler.start_browser()
        log_message("🔑 네이버 로그인이 필요한 경우 브라우저 창에서 진행해 주세요. (5초 대기...)")
        time.sleep(5.0)
        
        # 운영진 정보 수집 시작
        leaders = crawler.extract_cafe_leaders(cafe_url_or_name)
        
        if leaders:
            st.session_state.marketer_leaders = leaders
            
            # 다운로드 폴더에 즉시 CSV 다이렉트 저장
            try:
                dl_dir = get_user_download_dir()
                # 파일명에서 특수문자 제거
                safe_name = re.sub(r'[\/:*?"<>|]', '', cafe_url_or_name).replace("https", "").replace("cafe.naver.com", "").strip("_")
                if not safe_name:
                    safe_name = "naver_cafe"
                csv_path = dl_dir / f"{safe_name}_운영진_이메일_목록.csv"
                
                df = pd.DataFrame(leaders)
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                log_message(f"💾 수집 결과가 다운로드 폴더에 저장되었습니다: {csv_path.name}")
                
                # 윈도우 탐색기 열기 및 포커싱
                os.startfile(dl_dir)
                log_message("📁 윈도우 탐색기를 자동으로 실행했습니다.")
            except Exception as e_save:
                log_message(f"⚠️ 파일 저장 또는 탐색기 기동 실패: {e_save}")
        else:
            log_message("❌ 추출된 운영진 정보가 없습니다.")
            
    except Exception as e:
        log_message(f"🚨 작업 중 치명적 에러 발생: {e}")
        log_message(traceback.format_exc())
    finally:
        if crawler:
            try:
                crawler.close()
                log_message("🔒 브라우저를 안전하게 종료했습니다.")
            except:
                pass
        st.session_state.marketer_running = False

def run_sending_job(method: str, target_list: list, subject: str, content: str, delay_min: int, delay_max: int, smtp_settings: dict = None):
    st.session_state.marketer_running = True
    st.session_state.marketer_stop_requested = False
    
    crawler = None
    try:
        total = len(target_list)
        st.session_state.marketer_send_progress = 0.0
        st.session_state.marketer_send_status_text = f"발송 대기 중 (총 {total}건)"
        
        if method == "쪽지":
            log_message("🌐 쪽지 발송용 undetected-chromedriver 브라우저 실행 중...")
            crawler = NaverCafeCrawler(debug_mode=True)
            def log_cb(msg):
                log_message(msg)
            crawler.set_status_callback(log_cb)
            crawler.start_browser()
            log_message("🔑 네이버 발송 계정 로그인이 필요합니다. (5초 대기...)")
            time.sleep(5.0)
            
            success_cnt = 0
            fail_cnt = 0
            
            for idx, item in enumerate(target_list):
                if st.session_state.marketer_stop_requested:
                    log_message("⚠️ 사용자에 의해 작업 중단이 요청되었습니다.")
                    break
                    
                target_id = item.get("naver_id")
                if not target_id:
                    continue
                    
                st.session_state.marketer_send_status_text = f"쪽지 발송 진행 중 ({idx+1}/{total})"
                st.session_state.marketer_send_progress = float(idx + 1) / float(total)
                
                log_message(f"[{idx+1}/{total}] [{target_id}] 쪽지 발송 시도...")
                try:
                    memo_url = f"https://note.naver.com/note/write.nhn?targetUserId={target_id}"
                    crawler.driver.get(memo_url)
                    time.sleep(2.0)
                    
                    crawler.driver.switch_to.default_content()
                    
                    # 제목 폼 입력
                    try:
                        title_input = crawler.driver.find_element(By.CSS_SELECTOR, "input[name='title'], #title")
                        title_input.clear()
                        title_input.send_keys(subject)
                    except:
                        pass
                        
                    # 내용 폼 입력
                    content_textarea = crawler.driver.find_element(By.CSS_SELECTOR, "textarea[name='noteContent'], #noteContent, textarea.write_area")
                    content_textarea.clear()
                    content_textarea.send_keys(content)
                    
                    # 보내기 클릭
                    send_btn = crawler.driver.find_element(By.CSS_SELECTOR, "button.btn_send, #btn_send, a.btn_send")
                    crawler.driver.execute_script("arguments[0].click();", send_btn)
                    time.sleep(1.5)
                    
                    # Alert 수락
                    try:
                        time.sleep(0.5)
                        crawler.driver.switch_to.alert.accept()
                    except:
                        pass
                        
                    success_cnt += 1
                    log_message(f"  => [성공] {target_id} 쪽지 발송 성공")
                except Exception as ex:
                    fail_cnt += 1
                    log_message(f"  => [실패] {target_id} 쪽지 발송 실패: {ex}")
                    
                # 대기
                if idx < total - 1 and not st.session_state.marketer_stop_requested:
                    delay = random.uniform(delay_min, delay_max)
                    log_message(f"  [대기] {delay:.1f}초 동안 휴식 대기 중 (봇 의심 방지)")
                    time.sleep(delay)
                    
            log_message(f"[쪽지 발송 완료] 총 {total}건 중 성공: {success_cnt}건, 실패: {fail_cnt}건")
            
        elif method == "이메일" and smtp_settings:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            server_host = smtp_settings["host"]
            server_port = int(smtp_settings["port"])
            smtp_user = smtp_settings["user"]
            smtp_pass = smtp_settings["pass"]
            
            log_message(f"📧 SMTP 서버 연결 시도: {server_host}:{server_port} | ID: {smtp_user}")
            
            success_cnt = 0
            fail_cnt = 0
            
            for idx, item in enumerate(target_list):
                if st.session_state.marketer_stop_requested:
                    log_message("⚠️ 사용자에 의해 작업 중단이 요청되었습니다.")
                    break
                    
                email = item.get("email")
                if not email:
                    continue
                    
                st.session_state.marketer_send_status_text = f"메일 발송 진행 중 ({idx+1}/{total})"
                st.session_state.marketer_send_progress = float(idx + 1) / float(total)
                
                log_message(f"[{idx+1}/{total}] [{email}] 메일 발송 시도...")
                try:
                    msg = MIMEMultipart()
                    sender_email = f"{smtp_user}@naver.com" if "naver" in server_host.lower() and "@" not in smtp_user else smtp_user
                    msg['From'] = sender_email
                    msg['To'] = email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(content, 'plain', 'utf-8'))
                    
                    if server_port == 465:
                        server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
                    else:
                        server = smtplib.SMTP(server_host, server_port, timeout=10)
                        server.starttls()
                        
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender_email, email, msg.as_string())
                    server.quit()
                    
                    success_cnt += 1
                    log_message(f"  => [성공] {email} 메일 발송 성공")
                except Exception as ex:
                    fail_cnt += 1
                    log_message(f"  => [실패] {email} 메일 발송 실패: {ex}")
                    
                # 대기
                if idx < total - 1 and not st.session_state.marketer_stop_requested:
                    delay = random.uniform(delay_min, delay_max)
                    log_message(f"  [대기] {delay:.1f}초 동안 휴식 대기 중 (봇 의심 방지)")
                    time.sleep(delay)
                    
            log_message(f"[메일 발송 완료] 총 {total}건 중 성공: {success_cnt}건, 실패: {fail_cnt}건")
            
    except Exception as e:
        log_message(f"🚨 발송 작업 중 치명적 에러: {e}")
        log_message(traceback.format_exc())
    finally:
        if crawler:
            try:
                crawler.close()
                log_message("🔒 발송 브라우저를 안전하게 종료했습니다.")
            except:
                pass
        st.session_state.marketer_running = False
        st.session_state.marketer_send_progress = 1.0
        st.session_state.marketer_send_status_text = "작업 완료"

# 5. UI 화면 그리기
inject_settings_three_cards_css(key_basename="marketer_settings_card")

col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    # 5-1. 운영진 추출 카드
    st.markdown('<div class="cafe-monster-settings-card">', unsafe_allow_html=True)
    render_settings_card_title("🔍 카페 운영진 정보 수집", icon="ia-info")
    
    target_cafe = st.text_input(
        "대상 카페 URL 또는 카페 영문 ID",
        value=config.get("marketer_target_cafe", ""),
        help="예: joonggonara 또는 https://cafe.naver.com/joonggonara"
    )
    
    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        run_extract = st.button(
            "운영진 추출 시작 🚀",
            use_container_width=True,
            type="primary",
            disabled=st.session_state.marketer_running
        )
    with btn_col2:
        stop_extract = st.button(
            "추출 작업 중단 🛑",
            use_container_width=True,
            type="secondary",
            disabled=not st.session_state.marketer_running
        )
        
    if run_extract and target_cafe.strip():
        # 설정 저장
        config["marketer_target_cafe"] = target_cafe.strip()
        save_config(config)
        
        st.session_state.marketer_logs = []
        log_message("운영진 추출 작업을 백그라운드 스레드로 시작합니다...")
        
        # 스레드 구동
        t = threading.Thread(target=run_extraction_job, args=(target_cafe.strip(),))
        st.session_state.marketer_thread = t
        t.start()
        st.rerun()
        
    if stop_extract:
        st.session_state.marketer_stop_requested = True
        log_message("작업 중단이 요청되었습니다. 진행 중인 루프 종료 대기 중...")
        st.rerun()
        
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 5-2. 자동 발송 설정 & 메시지 템플릿 카드
    st.markdown('<div class="cafe-monster-settings-card" style="margin-top: 15px;">', unsafe_allow_html=True)
    render_settings_card_title("✉️ 자동 발송 메시지 템플릿 설정", icon="mail")
    
    send_method = st.radio(
        "발송 수단 선택",
        options=["쪽지", "이메일"],
        index=0 if config.get("marketer_send_method", "쪽지") == "쪽지" else 1,
        horizontal=True
    )
    
    # 딜레이 조절 슬라이더
    delay_range = st.slider(
        "발송 간격 딜레이 (초) - 랜덤 휴식 적용",
        min_value=5,
        max_value=300,
        value=(config.get("marketer_delay_min", 30), config.get("marketer_delay_max", 120)),
        step=5,
        help="단시간 발송 차단을 막기 위해 지연 간격을 루즈하게 설정하는 것을 강력 추천합니다."
    )
    
    # 쪽지 폼
    if send_method == "쪽지":
        memo_subj = st.text_input("쪽지 제목", value=config.get("marketer_memo_subject", "[제안] 카페몬스터 마케팅 프로그램 소개"))
        memo_content = st.text_area("쪽지 본문 내용", value=config.get("marketer_memo_content", "안녕하세요 매니저님,\n카페몬스터에서 개발한 타겟 스크래핑 프로그램을 소개합니다..."), height=150)
    else:
        # 이메일 SMTP 폼
        smtp_srv = st.text_input("SMTP 서버 주소", value=config.get("marketer_smtp_server", "smtp.naver.com"))
        smtp_prt = st.number_input("SMTP 포트 번호", value=config.get("marketer_smtp_port", 465), step=1)
        smtp_usr = st.text_input("SMTP 로그인 계정 ID (네이버 ID)", value=config.get("marketer_smtp_user", ""))
        smtp_pwd = st.text_input("SMTP 앱 비밀번호 (2차 비밀번호)", value=config.get("marketer_smtp_password", ""), type="password")
        
        memo_subj = st.text_input("이메일 제목", value=config.get("marketer_email_subject", "[제안] 카페몬스터 마케팅 프로그램 소개"))
        memo_content = st.text_area("이메일 본문 내용", value=config.get("marketer_email_content", "안녕하세요 매니저님,\n카페몬스터에서 개발한 타겟 스크래핑 프로그램을 소개합니다..."), height=150)
        
    btn_send_run = st.button(
        "자동 발송 시작 ✈️",
        use_container_width=True,
        type="primary",
        disabled=st.session_state.marketer_running or not st.session_state.marketer_leaders
    )
    
    if btn_send_run:
        # 설정 저장
        config["marketer_send_method"] = send_method
        config["marketer_delay_min"] = delay_range[0]
        config["marketer_delay_max"] = delay_range[1]
        if send_method == "쪽지":
            config["marketer_memo_subject"] = memo_subj
            config["marketer_memo_content"] = memo_content
        else:
            config["marketer_smtp_server"] = smtp_srv
            config["marketer_smtp_port"] = smtp_prt
            config["marketer_smtp_user"] = smtp_usr
            config["marketer_smtp_password"] = smtp_pwd
            config["marketer_email_subject"] = memo_subj
            config["marketer_email_content"] = memo_content
        save_config(config)
        
        st.session_state.marketer_logs = []
        log_message(f"자동 {send_method} 발송 작업을 스레드로 구동합니다...")
        
        smtp_set = None
        if send_method == "이메일":
            smtp_set = {
                "host": smtp_srv,
                "port": smtp_prt,
                "user": smtp_usr,
                "pass": smtp_pwd
            }
            
        t = threading.Thread(
            target=run_sending_job,
            args=(send_method, st.session_state.marketer_leaders, memo_subj, memo_content, delay_range[0], delay_range[1], smtp_set)
        )
        st.session_state.marketer_thread = t
        t.start()
        st.rerun()
        
    st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    # 5-3. 실시간 작업 진행 상태 및 로그 카드
    st.markdown('<div class="cafe-monster-settings-card">', unsafe_allow_html=True)
    render_settings_card_title("📊 작업 진행 모니터링", icon="cpu")
    
    # 진행률 표시
    if st.session_state.marketer_running:
        st.progress(st.session_state.marketer_send_progress)
        st.info(st.session_state.marketer_send_status_text)
        
    # 로그 스크롤 박스 (3Monster 규정 준수 - 무제한 스크롤박스 형태)
    log_content = "\n".join(st.session_state.marketer_logs)
    log_html = f"""
    <div style="
        background-color: #0f172a;
        color: #38bdf8;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.85rem;
        padding: 12px;
        border-radius: 8px;
        height: 380px;
        overflow-y: scroll;
        white-space: pre-wrap;
        border: 1px solid #334155;
    ">{html.escape(log_content)}</div>
    """
    st.markdown(log_html, unsafe_allow_html=True)
    
    # 로그 클립보드 복사 및 고객센터 링크 연동
    col_log_btn1, col_log_btn2 = st.columns([1, 1])
    with col_log_btn1:
        # Streamlit 내장 copy
        st.download_button(
            "📋 전체 로그 파일 다운로드",
            data=log_content,
            file_name=f"marketer_log_{datetime.now().strftime('%Y%md_%H%M%S')}.log",
            mime="text/plain",
            use_container_width=True
        )
    with col_log_btn2:
        # 고객센터로 바로가기 링크 (3Monster 보안 규정 - 고객지원 쇼룸 노출 유도)
        st.markdown(
            '<a href="https://kmong.com" target="_blank" style="text-decoration:none;"><button style="width:100%;height:38px;border-radius:4px;border:1px solid #cbd5e1;background:#ffffff;color:#1e3a8a;font-weight:600;cursor:pointer;">💬 3Monster 1:1 고객센터</button></a>',
            unsafe_allow_html=True
        )
        
    st.markdown("</div>", unsafe_allow_html=True)

# 6. 하단 데이터 리스트 표출
if st.session_state.marketer_leaders:
    st.subheader("📋 수집된 운영진 리스트")
    df_leaders = pd.DataFrame(st.session_state.marketer_leaders)
    st.dataframe(df_leaders, use_container_width=True)
