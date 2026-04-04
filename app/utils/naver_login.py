import time
import random


def _has_naver_login_cookie(crawler_obj) -> bool:
    try:
        if not crawler_obj or not getattr(crawler_obj, "driver", None):
            return False
        cookie_names = {str(c.get("name", "")).upper() for c in (crawler_obj.driver.get_cookies() or [])}
        return ("NID_SES" in cookie_names) or ("NID_AUT" in cookie_names)
    except Exception:
        return False


def _is_captcha_like_page(driver) -> bool:
    try:
        cur_url = str(getattr(driver, "current_url", "") or "").lower()
        title = str(getattr(driver, "title", "") or "").lower()
        keys = ["captcha", "캡차", "자동입력", "robot", "recaptcha"]
        if any(k in cur_url for k in keys):
            return True
        if any(k in title for k in keys):
            return True
        try:
            body_text = str(
                driver.execute_script(
                    "return (document.body && (document.body.innerText || '').slice(0, 2000)) || '';"
                )
                or ""
            ).lower()
            return any(k in body_text for k in keys)
        except Exception:
            return False
    except Exception:
        return False


def auto_login_naver_with_js(crawler_obj, user_id: str, user_pw: str) -> tuple:
    """네이버 자동 로그인 - id_el/pw_el 직접 참조 JS 입력."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        if not crawler_obj or not getattr(crawler_obj, "driver", None):
            return False, "드라이버 없음"
        driver = crawler_obj.driver
        uid = str(user_id or "").strip()
        upw = str(user_pw or "")
        if (not uid) or (not upw):
            return False, "아이디/비밀번호 미입력"

        if _has_naver_login_cookie(crawler_obj):
            return True, "기존 세션 유지"

        driver.get("https://nid.naver.com/nidlogin.login?mode=form&url=https://cafe.naver.com/")
        time.sleep(random.uniform(1.0, 1.8))

        if _is_captcha_like_page(driver):
            return False, "캡챠 감지"

        wait = WebDriverWait(driver, 10)
        id_el = wait.until(EC.presence_of_element_located((By.ID, "id")))
        pw_el = wait.until(EC.presence_of_element_located((By.ID, "pw")))

        driver.execute_script(
            """
            const idEl = arguments[0], pwEl = arguments[1],
                  uid  = arguments[2], upw  = arguments[3];
            idEl.focus(); idEl.value = uid;
            idEl.dispatchEvent(new Event('input',  {bubbles: true}));
            idEl.dispatchEvent(new Event('change', {bubbles: true}));
            pwEl.focus(); pwEl.value = upw;
            pwEl.dispatchEvent(new Event('input',  {bubbles: true}));
            pwEl.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            id_el, pw_el, uid, upw,
        )
        time.sleep(random.uniform(0.3, 0.6))

        if _is_captcha_like_page(driver):
            return False, "캡챠 감지(입력 후)"

        try:
            login_btn = driver.find_element(By.CSS_SELECTOR, "#log\\.login, button[type='submit']")
            login_btn.click()
        except Exception:
            return False, "로그인 버튼 클릭 실패"

        time.sleep(random.uniform(1.8, 2.5))

        if _has_naver_login_cookie(crawler_obj):
            return True, "로그인 성공"
        cur_url = str(getattr(driver, "current_url", "") or "")
        if "nid.naver.com" not in cur_url:
            return True, "로그인 성공(페이지 이동 확인)"

        if _is_captcha_like_page(driver):
            return False, "캡챠 감지(로그인 후)"

        # 2단계 인증(OTP) 대기: 모바일 알림 확인 필요
        body_text = ""
        try:
            body_text = str(driver.execute_script(
                "return (document.body && document.body.innerText.slice(0, 2000)) || '';"
            ) or "")
        except Exception:
            pass
        two_step_keywords = ["2단계 인증", "인증 알림", "OTP", "인증번호를 입력"]
        if any(kw in body_text for kw in two_step_keywords):
            _status_cb = getattr(crawler_obj, "_status_callback", None)
            if _status_cb:
                _status_cb("📱 2단계 인증 알림 발송됨 — 모바일에서 인증을 완료해주세요 (최대 60초 대기)")
            for _poll in range(30):
                time.sleep(2)
                if _has_naver_login_cookie(crawler_obj):
                    return True, "로그인 성공(2단계 인증 완료)"
                try:
                    poll_url = str(getattr(driver, "current_url", "") or "")
                    if "nid.naver.com" not in poll_url:
                        return True, "로그인 성공(2단계 인증 후 페이지 이동)"
                except Exception:
                    pass
            return False, "2단계 인증 시간 초과 — 브라우저에서 수동 인증 필요"

        return False, "세션 쿠키 확인 실패 - 수동 로그인 필요"
    except Exception as e:
        return False, f"예외: {e}"
