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
    page_title="카페스탭 ID 수집 - CafeScraper",
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

# 2. 전역 작업 상태 관리 (스레드 세션 동기화 해결용)
if "MARKETER_JOBS" not in st.session_state:
    # 핫 리로드 시 유실 방지를 위해 session_state에 보관하거나 글로벌 선언
    st.session_state.MARKETER_JOBS = {}
MARKETER_JOBS = st.session_state.MARKETER_JOBS

# 세션 상태 기본값 정의
if "marketer_logs" not in st.session_state:
    st.session_state.marketer_logs = []
if "marketer_leaders" not in st.session_state:
    st.session_state.marketer_leaders = []
if "marketer_running" not in st.session_state:
    st.session_state.marketer_running = False
if "marketer_stop_requested" not in st.session_state:
    st.session_state.marketer_stop_requested = False
if "marketer_active_job_id" not in st.session_state:
    st.session_state.marketer_active_job_id = None

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

def log_to_job(job_id: str, msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if job_id in MARKETER_JOBS:
        MARKETER_JOBS[job_id]["logs"].append(f"[{timestamp}] {msg}")

# 4. 백그라운드 작업 스레드 함수
def run_extraction_job(job_id: str, mode: str, text_input: str, search_keyword: str, max_cafes: int):
    if job_id not in MARKETER_JOBS:
        return
    MARKETER_JOBS[job_id]["running"] = True
    
    # 1. 카페 목록 준비
    target_cafes = []
    if mode == "직접 입력":
        lines = [line.strip() for line in text_input.split("\n") if line.strip()]
        for line in lines:
            target_cafes.append(line)
    else:
        log_to_job(job_id, f"🔍 키워드 '{search_keyword}'로 네이버 카페 검색을 진행합니다...")
        import urllib.parse
        import requests
        from bs4 import BeautifulSoup
        import re
        
        cafe_ids = set()
        for page_idx in range(3):
            if MARKETER_JOBS[job_id]["stop_requested"]:
                break
            start_num = page_idx * 15 + 1
            encoded = urllib.parse.quote(search_keyword)
            search_url = f"https://search.naver.com/search.naver?where=cafe&query={encoded}&start={start_num}"
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                res = requests.get(search_url, headers=headers, timeout=10)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    links = soup.find_all("a")
                    for link in links:
                        href = link.get("href", "")
                        if "cafe.naver.com" in href:
                            match = re.search(r"cafe\.naver\.com/([a-zA-Z0-9_]+)", href)
                            if match:
                                cid = match.group(1)
                                if cid not in ("ca-fe", "ArticleRead", "ArticleList", "MyCafeIntro"):
                                    cafe_ids.add(cid)
            except Exception as e_search:
                log_to_job(job_id, f"  ⚠️ 검색 {page_idx+1}페이지 수집 중 에러: {e_search}")
            time.sleep(0.5)
            
        target_cafes = sorted(list(cafe_ids))[:max_cafes]
        log_to_job(job_id, f"  └ [성공] 총 {len(target_cafes)}개의 카페 ID를 수집했습니다: {', '.join(target_cafes)}")
        
    if not target_cafes:
        log_to_job(job_id, "❌ 수집할 대상 카페가 존재하지 않습니다.")
        MARKETER_JOBS[job_id]["running"] = False
        return

    crawler = None
    all_leaders = []
    try:
        log_to_job(job_id, "🌐 undetected-chromedriver 브라우저 실행 중...")
        crawler = NaverCafeCrawler(debug_mode=True)
        
        def crawler_log_callback(msg):
            log_to_job(job_id, msg)
        crawler.set_status_callback(crawler_log_callback)
        
        crawler.start_browser()
        log_to_job(job_id, "🔑 네이버 로그인이 필요한 경우 브라우저 창에서 진행해 주세요. (5초 대기...)")
        time.sleep(5.0)
        
        for idx, cafe in enumerate(target_cafes):
            if MARKETER_JOBS[job_id]["stop_requested"]:
                log_to_job(job_id, "⚠️ 사용자에 의해 작업 중단이 요청되었습니다.")
                break
                
            log_to_job(job_id, f"🔄 [{idx+1}/{len(target_cafes)}] '{cafe}' 스탭 추출 시작...")
            try:
                leaders = crawler.extract_cafe_leaders(cafe)
                if leaders:
                    for l in leaders:
                        l['source_cafe'] = cafe
                    all_leaders.extend(leaders)
                    log_to_job(job_id, f"  => 성공: {len(leaders)}명 추출 완료")
                else:
                    log_to_job(job_id, "  => 추출된 스탭 정보가 없습니다.")
            except Exception as e_cafe:
                log_to_job(job_id, f"  => 에러 발생: {e_cafe}")
                
            time.sleep(random.uniform(1.5, 3.0))
            
        if all_leaders:
            MARKETER_JOBS[job_id]["leaders"] = all_leaders
            
            try:
                dl_dir = get_user_download_dir()
                safe_name = search_keyword.strip() if mode == "키워드 검색" else "직접입력"
                safe_name = re.sub(r'[\/:*?"<>|]', '', safe_name)
                if not safe_name:
                    safe_name = "naver_cafe"
                csv_path = dl_dir / f"{safe_name}_스탭_이메일_목록.csv"
                
                df = pd.DataFrame(all_leaders)
                if 'source_cafe' in df.columns:
                    cols = ['source_cafe'] + [c for c in df.columns if c != 'source_cafe']
                    df = df[cols]
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                log_to_job(job_id, f"💾 수집 결과가 다운로드 폴더에 저장되었습니다: {csv_path.name}")
                
                os.startfile(dl_dir)
                log_to_job(job_id, "📁 윈도우 탐색기를 자동으로 실행했습니다.")
            except Exception as e_save:
                log_to_job(job_id, f"⚠️ 파일 저장 또는 탐색기 기동 실패: {e_save}")
        else:
            log_to_job(job_id, "❌ 추출된 최종 스탭 정보가 하나도 없습니다.")
            
    except Exception as e:
        log_to_job(job_id, f"🚨 작업 중 치명적 에러 발생: {e}")
        log_to_job(job_id, traceback.format_exc())
    finally:
        if crawler:
            try:
                crawler.close()
                log_to_job(job_id, "🔒 브라우저를 안전하게 종료했습니다.")
            except:
                pass
        MARKETER_JOBS[job_id]["running"] = False

def run_sending_job(job_id: str, method: str, target_list: list, subject: str, content: str, delay_min: int, delay_max: int, smtp_settings: dict = None):
    if job_id not in MARKETER_JOBS:
        return
    MARKETER_JOBS[job_id]["running"] = True
    
    crawler = None
    try:
        total = len(target_list)
        MARKETER_JOBS[job_id]["progress"] = 0.0
        MARKETER_JOBS[job_id]["status_text"] = f"발송 대기 중 (총 {total}건)"
        
        if method == "쪽지":
            log_to_job(job_id, "🌐 쪽지 발송용 undetected-chromedriver 브라우저 실행 중...")
            crawler = NaverCafeCrawler(debug_mode=True)
            def log_cb(msg):
                log_to_job(job_id, msg)
            crawler.set_status_callback(log_cb)
            crawler.start_browser()
            log_to_job(job_id, "🔑 네이버 발송 계정 로그인이 필요합니다. (5초 대기...)")
            time.sleep(5.0)
            
            success_cnt = 0
            fail_cnt = 0
            
            for idx, item in enumerate(target_list):
                if MARKETER_JOBS[job_id]["stop_requested"]:
                    log_to_job(job_id, "⚠️ 사용자에 의해 작업 중단이 요청되었습니다.")
                    break
                    
                target_id = item.get("naver_id")
                if not target_id:
                    continue
                    
                MARKETER_JOBS[job_id]["status_text"] = f"쪽지 발송 진행 중 ({idx+1}/{total})"
                MARKETER_JOBS[job_id]["progress"] = float(idx + 1) / float(total)
                
                log_to_job(job_id, f"[{idx+1}/{total}] [{target_id}] 쪽지 발송 시도...")
                try:
                    memo_url = f"https://note.naver.com/note/write.nhn?targetUserId={target_id}"
                    crawler.driver.get(memo_url)
                    time.sleep(2.0)
                    
                    crawler.driver.switch_to.default_content()
                    
                    try:
                        title_input = crawler.driver.find_element(By.CSS_SELECTOR, "input[name='title'], #title")
                        title_input.clear()
                        title_input.send_keys(subject)
                    except:
                        pass
                        
                    content_textarea = crawler.driver.find_element(By.CSS_SELECTOR, "textarea[name='noteContent'], #noteContent, textarea.write_area")
                    content_textarea.clear()
                    content_textarea.send_keys(content)
                    
                    send_btn = crawler.driver.find_element(By.CSS_SELECTOR, "button.btn_send, #btn_send, a.btn_send")
                    crawler.driver.execute_script("arguments[0].click();", send_btn)
                    time.sleep(1.5)
                    
                    try:
                        time.sleep(0.5)
                        crawler.driver.switch_to.alert.accept()
                    except:
                        pass
                        
                    success_cnt += 1
                    log_to_job(job_id, f"  => [성공] {target_id} 쪽지 발송 성공")
                except Exception as ex:
                    fail_cnt += 1
                    log_to_job(job_id, f"  => [실패] {target_id} 쪽지 발송 실패: {ex}")
                    
                if idx < total - 1 and not MARKETER_JOBS[job_id]["stop_requested"]:
                    delay = random.uniform(delay_min, delay_max)
                    log_to_job(job_id, f"  [대기] {delay:.1f}초 동안 휴식 대기 중 (봇 의심 방지)")
                    time.sleep(delay)
                    
            log_to_job(job_id, f"[쪽지 발송 완료] 총 {total}건 중 성공: {success_cnt}건, 실패: {fail_cnt}건")
            
        elif method == "이메일" and smtp_settings:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            server_host = smtp_settings["host"]
            server_port = int(smtp_settings["port"])
            smtp_user = smtp_settings["user"]
            smtp_pass = smtp_settings["pass"]
            
            log_to_job(job_id, f"📧 SMTP 서버 연결 시도: {server_host}:{server_port} | ID: {smtp_user}")
            
            success_cnt = 0
            fail_cnt = 0
            
            for idx, item in enumerate(target_list):
                if MARKETER_JOBS[job_id]["stop_requested"]:
                    log_to_job(job_id, "⚠️ 사용자에 의해 작업 중단이 요청되었습니다.")
                    break
                    
                email = item.get("email")
                if not email:
                    continue
                    
                MARKETER_JOBS[job_id]["status_text"] = f"메일 발송 진행 중 ({idx+1}/{total})"
                MARKETER_JOBS[job_id]["progress"] = float(idx + 1) / float(total)
                
                log_to_job(job_id, f"[{idx+1}/{total}] [{email}] 메일 발송 시도...")
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
                    log_to_job(job_id, f"  => [성공] {email} 메일 발송 성공")
                except Exception as ex:
                    fail_cnt += 1
                    log_to_job(job_id, f"  => [실패] {email} 메일 발송 실패: {ex}")
                    
                if idx < total - 1 and not MARKETER_JOBS[job_id]["stop_requested"]:
                    delay = random.uniform(delay_min, delay_max)
                    log_to_job(job_id, f"  [대기] {delay:.1f}초 동안 휴식 대기 중 (봇 의심 방지)")
                    time.sleep(delay)
                    
            log_to_job(job_id, f"[메일 발송 완료] 총 {total}건 중 성공: {success_cnt}건, 실패: {fail_cnt}건")
            
    except Exception as e:
        log_to_job(job_id, f"🚨 발송 작업 중 치명적 에러: {e}")
        log_to_job(job_id, traceback.format_exc())
    finally:
        if crawler:
            try:
                crawler.close()
                log_to_job(job_id, "🔒 발송 브라우저를 안전하게 종료했습니다.")
            except:
                pass
        MARKETER_JOBS[job_id]["running"] = False
        MARKETER_JOBS[job_id]["progress"] = 1.0
        MARKETER_JOBS[job_id]["status_text"] = "작업 완료"

# 5. 백그라운드 스레드 상태 동기화 처리
active_job_id = st.session_state.get("marketer_active_job_id")
if active_job_id and active_job_id in MARKETER_JOBS:
    job = MARKETER_JOBS[active_job_id]
    st.session_state.marketer_logs = job["logs"]
    st.session_state.marketer_send_progress = job["progress"]
    st.session_state.marketer_send_status_text = job["status_text"]
    st.session_state.marketer_running = job["running"]
    st.session_state.marketer_stop_requested = job["stop_requested"]
    if "leaders" in job:
        st.session_state.marketer_leaders = job["leaders"]
    if not job["running"]:
        # 작업 종료 시
        st.session_state.marketer_active_job_id = None

# 6. UI 화면 그리기
inject_settings_three_cards_css(key_basename="marketer_settings_card")

st.markdown("#### ⚙️ 카페스탭 ID 수집 설정")
_t1, _t2, _t3 = st.columns([1, 1, 1], gap="medium")

with _t1:
    with st.container(border=True, key="marketer_settings_card_1"):
        render_settings_card_title("카페스탭 ID 수집", icon="🔍")
        
        target_mode = st.radio(
            "수집 방식 선택",
            options=["직접 입력", "키워드 검색"],
            index=0 if config.get("marketer_target_mode", "직접 입력") == "직접 입력" else 1,
            horizontal=True
        )
        
        if target_mode == "직접 입력":
            target_cafes_input = st.text_area(
                "대상 카페 URL 또는 ID (한 줄에 하나씩 입력)",
                value=config.get("marketer_target_cafes_input", "joonggonara\nhttps://cafe.naver.com/campingfirst"),
                height=120,
                help="수십 개의 카페 주소나 영문 ID를 한 줄에 하나씩 여러 개 입력할 수 있습니다."
            )
            search_keyword = ""
            max_cafes = 1
        else:
            search_keyword = st.text_input(
                "검색 키워드 입력",
                value=config.get("marketer_search_keyword", "캠핑"),
                help="네이버에서 이 키워드로 카페를 검색하여 대상 목록을 자동 확보합니다."
            )
            max_cafes = st.number_input(
                "최대 수집 카페 수",
                min_value=1,
                max_value=100,
                value=int(config.get("marketer_max_cafes", 20)),
                step=5,
                help="수집할 카페 개수의 최대 한도를 설정합니다."
            )
            target_cafes_input = ""
            
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            run_extract = st.button(
                "추출 시작 🚀",
                use_container_width=True,
                type="primary",
                disabled=st.session_state.marketer_running
            )
        with btn_col2:
            stop_extract = st.button(
                "추출 중단 🛑",
                use_container_width=True,
                type="secondary",
                disabled=not st.session_state.marketer_running
            )
            
        if run_extract:
            # 설정 저장
            config["marketer_target_mode"] = target_mode
            if target_mode == "직접 입력":
                config["marketer_target_cafes_input"] = target_cafes_input
            else:
                config["marketer_search_keyword"] = search_keyword
                config["marketer_max_cafes"] = max_cafes
            save_config(config)
            
            # 스레드 작업 신규 등록
            job_id = str(uuid.uuid4())
            MARKETER_JOBS[job_id] = {
                "logs": [],
                "progress": 0.0,
                "status_text": "수집 준비 중...",
                "running": True,
                "stop_requested": False,
                "leaders": []
            }
            st.session_state.marketer_active_job_id = job_id
            st.session_state.marketer_running = True
            st.session_state.marketer_stop_requested = False
            
            log_to_job(job_id, "카페 스탭 추출 작업을 백그라운드 스레드로 시작합니다...")
            
            # 스레드 구동
            t = threading.Thread(
                target=run_extraction_job,
                args=(job_id, target_mode, target_cafes_input, search_keyword, max_cafes),
                daemon=True
            )
            t.start()
            st.rerun()
            
        if stop_extract:
            active_job_id = st.session_state.get("marketer_active_job_id")
            if active_job_id and active_job_id in MARKETER_JOBS:
                MARKETER_JOBS[active_job_id]["stop_requested"] = True
                log_to_job(active_job_id, "작업 중단이 요청되었습니다. 진행 중인 루프 종료 대기 중...")
            st.session_state.marketer_stop_requested = True
            st.rerun()

with _t2:
    with st.container(border=True, key="marketer_settings_card_2"):
        render_settings_card_title("메일 & 쪽지 자동발송", icon="✉️")
        
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
            memo_content = st.text_area("쪽지 본문 내용", value=config.get("marketer_memo_content", "안녕하세요 매니저님,\n카페몬스터에서 개발한 타겟 스크래핑 프로그램을 소개합니다..."), height=120)
        else:
            # 메일 연동 설정
            mail_host = st.text_input("메일 발송 서버 주소", value=config.get("marketer_smtp_server", "smtp.naver.com"))
            mail_port = st.number_input("메일 서버 포트 번호", value=config.get("marketer_smtp_port", 465), step=1)
            mail_user = st.text_input("발송용 메일 계정 ID (네이버 ID)", value=config.get("marketer_smtp_user", ""))
            mail_pass = st.text_input("발송용 앱 비밀번호 (2차 암호)", value=config.get("marketer_smtp_password", ""), type="password")
            
            memo_subj = st.text_input("이메일 제목", value=config.get("marketer_email_subject", "[제안] 카페몬스터 마케팅 프로그램 소개"))
            memo_content = st.text_area("이메일 본문 내용", value=config.get("marketer_email_content", "안녕하세요 매니저님,\n카페몬스터에서 개발한 타겟 스크래핑 프로그램을 소개합니다..."), height=120)
            
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
                config["marketer_smtp_server"] = mail_host
                config["marketer_smtp_port"] = mail_port
                config["marketer_smtp_user"] = mail_user
                config["marketer_smtp_password"] = mail_pass
                config["marketer_email_subject"] = memo_subj
                config["marketer_email_content"] = memo_content
            save_config(config)
            
            # 발송 스레드 작업 등록
            job_id = str(uuid.uuid4())
            MARKETER_JOBS[job_id] = {
                "logs": [],
                "progress": 0.0,
                "status_text": "발송 준비 중...",
                "running": True,
                "stop_requested": False,
                "leaders": st.session_state.marketer_leaders
            }
            st.session_state.marketer_active_job_id = job_id
            st.session_state.marketer_running = True
            st.session_state.marketer_stop_requested = False
            
            log_to_job(job_id, f"자동 {send_method} 발송 작업을 스레드로 구동합니다...")
            
            smtp_set = None
            if send_method == "이메일":
                smtp_set = {
                    "host": mail_host,
                    "port": mail_port,
                    "user": mail_user,
                    "pass": mail_pass
                }
                
            t = threading.Thread(
                target=run_sending_job,
                args=(job_id, send_method, st.session_state.marketer_leaders, memo_subj, memo_content, delay_range[0], delay_range[1], smtp_set),
                daemon=True
            )
            t.start()
            st.rerun()

with _t3:
    with st.container(border=True, key="marketer_settings_card_3"):
        render_settings_card_title("작업 진행 모니터링", icon="📊")
        
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
            height: 250px;
            overflow-y: scroll;
            white-space: pre-wrap;
            border: 1px solid #334155;
        ">{html.escape(log_content)}</div>
        """
        st.markdown(log_html, unsafe_allow_html=True)
        
        # 로그 클립보드 복사 및 고객센터 링크 연동
        col_log_btn1, col_log_btn2 = st.columns([1, 1])
        with col_log_btn1:
            st.download_button(
                "📋 로그 다운로드",
                data=log_content,
                file_name=f"marketer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                mime="text/plain",
                use_container_width=True
            )
        with col_log_btn2:
            st.markdown(
                '<a href="https://kmong.com" target="_blank" style="text-decoration:none;"><button style="width:100%;height:38px;border-radius:4px;border:1px solid #cbd5e1;background:#ffffff;color:#1e3a8a;font-weight:600;cursor:pointer;">💬 3Monster 고객센터</button></a>',
                unsafe_allow_html=True
            )

# 7. 하단 데이터 리스트 표출
if st.session_state.marketer_leaders:
    st.markdown("---")
    st.subheader("📋 수집된 운영진 리스트")
    df_leaders = pd.DataFrame(st.session_state.marketer_leaders)
    st.dataframe(df_leaders, use_container_width=True)

# 8. 백그라운드 동작 시 지속적인 UI 리플레시 폴링 루프
if st.session_state.get("marketer_running", False):
    time.sleep(1.0)
    st.rerun()
