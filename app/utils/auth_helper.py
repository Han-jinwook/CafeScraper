# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
import requests
import datetime
import time
from 라이브러리.auth import MonsterAuth

logger = logging.getLogger(__name__)

# Two-Track Storage Policy: %APPDATA%/MarketingMonster/CafeScraper
if sys.platform == "win32":
    USER_SETTINGS_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MarketingMonster", "CafeScraper")
else:
    USER_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".config", "MarketingMonster", "CafeScraper")

LICENSE_FILE = os.path.join(USER_SETTINGS_PATH, "license.dat")
CACHE_FILE = os.path.join(USER_SETTINGS_PATH, "license_cache.json")
TRIAL_SETTINGS_FILE = os.path.join(USER_SETTINGS_PATH, "trial_settings.json")
SUPABASE_URL = "https://suwinftalfgybvrnzruz.supabase.co"
SUPABASE_KEY = "sb_publishable_jUwQ1BWvG6F2H9GyELUoFw_mUOHbgWD"

class CafeMonsterAuthHelper:
    _cached_active_products = None
    _cached_limits = {}  # product_id -> limit
    _cached_exp_dates = {}  # product_id -> exp_date_str
    _cached_license_types = {}  # product_id -> license_type_str
    _hwid = None

    @classmethod
    def get_current_product_id(cls) -> str:
        """현재 실행 중인 에디션(CafeCrawler, EventStats, AutoComment)의 product_id를 식별합니다."""
        try:
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            mode_file = os.path.join(exe_dir, "mode.txt")
            if os.path.exists(mode_file):
                with open(mode_file, "r", encoding="utf-8") as f:
                    mode = f.read().strip().upper()
                    if mode == "PRO_CAFECRAWLER": return "CafeCrawler"
                    if mode == "PRO_EVENTSTATS": return "EventStats"
                    if mode == "PRO_AUTOCOMMENT": return "AutoComment"
                    if mode == "TRIAL": return "CafeCrawler"
        except Exception:
            pass
        exe_stem = os.path.splitext(os.path.basename(sys.executable))[0]
        if "EventStats" in exe_stem: return "EventStats"
        if "AutoComment" in exe_stem: return "AutoComment"
        if "CafeCrawler" in exe_stem: return "CafeCrawler"
        return "CafeCrawler"

    @classmethod
    def get_user_settings_path(cls) -> str:
        prod_id = cls.get_current_product_id()
        if sys.platform == "win32":
            p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MarketingMonster", prod_id)
        else:
            p = os.path.join(os.path.expanduser("~"), ".config", "MarketingMonster", prod_id)
        os.makedirs(p, exist_ok=True)
        return p

    @classmethod
    def get_license_file_path(cls) -> str:
        return os.path.join(cls.get_user_settings_path(), "license.dat")

    @classmethod
    def get_cache_file_path(cls) -> str:
        return os.path.join(cls.get_user_settings_path(), "license_cache.json")

    @classmethod
    def get_trial_settings_file_path(cls) -> str:
        return os.path.join(cls.get_user_settings_path(), "trial_settings.json")

    @classmethod
    def get_hwid(cls) -> str:
        if not cls._hwid:
            try:
                auth_temp = MonsterAuth(product_id="CafeCrawler", license_key="")
                cls._hwid = auth_temp._get_hwid()
            except Exception as e:
                logger.error(f"Error fetching HWID via MonsterAuth: {e}")
                cls._hwid = "UNKNOWN_HWID"
            return cls._hwid

    @classmethod
    def load_saved_keys(cls) -> list[str]:
        lic_file = cls.get_license_file_path()
        if not os.path.exists(lic_file):
            return []
        try:
            with open(lic_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []

    @classmethod
    def save_key(cls, key: str) -> bool:
        """새 라이선스 키를 로컬 파일에 추가 저장합니다."""
        try:
            lic_file = cls.get_license_file_path()
            keys = cls.load_saved_keys()
            if key not in keys:
                keys.append(key)
                os.makedirs(os.path.dirname(lic_file), exist_ok=True)
                with open(lic_file, "w", encoding="utf-8") as f:
                    for k in keys:
                        f.write(f"{k}\n")
            # 캐시 무효화
            cls._cached_active_products = None
            cls.clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to save license key: {e}")
            return False

    @classmethod
    def remove_key(cls, key: str) -> bool:
        try:
            keys = cls.load_saved_keys()
            if key in keys:
                keys.remove(key)
                os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
                with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                    for k in keys:
                        f.write(f"{k}\n")
            cls._cached_active_products = None
            cls.clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to remove license key: {e}")
            return False

    @classmethod
    def clear_cache(cls):
        cls._cached_active_products = None
        cls._cached_limits = {}
        cls._cached_exp_dates = {}
        cls._cached_license_types = {}
        cache_path = cls.get_cache_file_path()
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except:
                pass
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
            except:
                pass

    @classmethod
    def get_active_products(cls) -> set[str]:
        """현재 실행 중인 단일 에디션(curr_prod) 전용 라이선스만 엄격히 검증하여 격리 반환합니다."""
        if cls._cached_active_products is not None:
            return cls._cached_active_products

        curr_prod = cls.get_current_product_id()
        
        # 0. 무료 체험판 패키지(TRIAL)는 모든 탭이 체험판으로 실행됨
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        mode_file = os.path.join(exe_dir, "mode.txt")
        if os.path.exists(mode_file):
            try:
                with open(mode_file, "r", encoding="utf-8") as f:
                    if f.read().strip().upper().startswith("TRIAL"):
                        cls._cached_active_products = set()
                        cls._cached_limits = {}
                        cls._cached_exp_dates = {}
                        cls._cached_license_types = {}
                        return set()
            except:
                pass

        # 1. 로컬 캐시 조회 (현재 에디션 전용 격리)
        local_cache = cls._read_local_cache()
        if local_cache is not None:
            prods = set(local_cache.get("products", []))
            cls._cached_limits = local_cache.get("limits", {})
            cls._cached_exp_dates = local_cache.get("exp_dates", {})
            cls._cached_license_types = local_cache.get("license_types", {})
            if curr_prod in prods:
                cls._cached_active_products = {curr_prod}
            else:
                cls._cached_active_products = set()
            return cls._cached_active_products

        # 2. 서버 및 키 검증
        hwid = cls.get_hwid()
        active_prods = set()
        limits = {}

        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

        # 2.1 HWID에 바인딩된 활성 라이선스 중 현재 실행 에디션(curr_prod)만 핀포인트 조회
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?bound_value=eq.{hwid}&product_id=eq.{curr_prod}&status=eq.active&select=product_id,expire_date,collection_limit,serial_key,first_run_date,license_type"
        try:
            res = requests.get(url, headers=headers, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    prod = item.get("product_id")
                    exp = item.get("expire_date")
                    limit = item.get("collection_limit")
                    key = item.get("serial_key")
                    first_run = item.get("first_run_date")
                    l_type = item.get("license_type")
                    # 만료일 체크
                    if exp:
                        try:
                            exp_clean = exp.replace('Z', '+00:00')
                            exp_dt = datetime.datetime.fromisoformat(exp_clean)
                            if exp_dt.timestamp() < datetime.datetime.now(datetime.timezone.utc).timestamp():
                                continue
                        except Exception:
                            pass
                    if prod and prod == curr_prod:
                        active_prods.add(prod)
                        limits[prod] = limit
                        cls._cached_exp_dates[prod] = exp
                        cls._cached_license_types[prod] = l_type
                        
                        # 실행일자(first_run_date) 누락 시 백필 수행
                        if not first_run and key:
                            try:
                                auth_prod = MonsterAuth(
                                    product_id=prod,
                                    license_key=key,
                                    supabase_url=SUPABASE_URL,
                                    supabase_key=SUPABASE_KEY
                                )
                                auth_prod.verify_license()
                            except Exception as ex:
                                logger.error(f"Failed to backfill first_run_date in get_active_products: {ex}")
        except Exception as e:
            logger.error(f"Failed to query active licenses by HWID: {e}")

        # 2.2 저장된 키들 유효성 검사 및 바인딩 시도 (현재 에디션 키만 적용)
        saved_keys = cls.load_saved_keys()
        for key in saved_keys:
            try:
                url_key = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?serial_key=eq.{key}&select=product_id,license_type,expire_date"
                res_key = requests.get(url_key, headers=headers, timeout=3.0)
                if res_key.status_code == 200:
                    key_data = res_key.json()
                    if key_data:
                        prod_id = key_data[0].get("product_id")
                        l_type = key_data[0].get("license_type")
                        exp = key_data[0].get("expire_date")
                        if prod_id == curr_prod and prod_id not in active_prods:
                            auth_prod = MonsterAuth(
                                product_id=prod_id,
                                license_key=key,
                                supabase_url=SUPABASE_URL,
                                supabase_key=SUPABASE_KEY
                            )
                            success, _, col_limit = auth_prod.verify_license()
                            if success:
                                active_prods.add(prod_id)
                                limits[prod_id] = col_limit
                                cls._cached_license_types[prod_id] = l_type
                                cls._cached_exp_dates[prod_id] = exp
            except Exception as e:
                logger.error(f"Failed to validate key {key}: {e}")

        cls._cached_active_products = active_prods
        cls._cached_limits = limits

        # 로컬 캐시에 쓰기
        cls._write_local_cache(active_prods, limits)
        return active_prods

    @classmethod
    def check_product_license(cls, product_id: str) -> tuple[bool, int | None]:
        """특정 제품의 정식 인증 여부 및 수집 한도를 확인합니다."""
        active = cls.get_active_products()
        if product_id in active:
            return True, cls._cached_limits.get(product_id)
        return False, None

    @classmethod
    def get_license_badge_html(cls, product_id: str) -> str:
        """해당 제품의 라이선스 플랜 및 만료 기간 배지 HTML을 생성합니다."""
        active = cls.get_active_products()
        if product_id not in active:
            return '<div style="margin-top:4px;"><span style="font-size:0.80rem; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-weight:600; border:1px solid #fca5a5;">🔒 무료 체험판 (100건 제한)</span></div>'
        
        limit = cls._cached_limits.get(product_id)
        exp_str = cls._cached_exp_dates.get(product_id)
        lic_type = (cls._cached_license_types.get(product_id) or "").upper()
        
        diff_days = None
        date_formatted = None
        if exp_str:
            try:
                exp_clean = exp_str.replace('Z', '+00:00')
                exp_dt = datetime.datetime.fromisoformat(exp_clean)
                # KST 기준 변환 (UTC+9)
                kst_tz = datetime.timezone(datetime.timedelta(hours=9))
                exp_dt_kst = exp_dt.astimezone(kst_tz)
                now_kst = datetime.datetime.now(kst_tz)
                diff_days = (exp_dt_kst.date() - now_kst.date()).days
                date_formatted = exp_dt_kst.strftime("%Y.%m.%d")
            except Exception:
                pass

        if limit:
            plan_name = f"STANDARD (1개월 / {limit:,}건 제한)"
        elif lic_type in ["3M", "PREMIUM"] or (diff_days is not None and diff_days > 45):
            plan_name = "PREMIUM (3개월 / 무제한)"
        elif lic_type in ["6M"]:
            plan_name = "6M (6개월 / 무제한)"
        elif lic_type in ["1Y"]:
            plan_name = "1Y (1년 / 무제한)"
        else:
            plan_name = "DELUXE (1개월 / 무제한)"
            
        badge_html = f'<div style="margin-top:4px; display:inline-flex; align-items:center; gap:6px; flex-wrap:wrap;"><span style="font-size:0.80rem; background:#dcfce7; color:#166534; padding:2px 8px; border-radius:4px; font-weight:600; border:1px solid #86efac;">✅ {plan_name}</span>'
        
        if date_formatted and diff_days is not None:
            if diff_days >= 0:
                badge_html += f'<span style="font-size:0.80rem; background:#e0f2fe; color:#075985; padding:2px 8px; border-radius:4px; font-weight:600; border:1px solid #7dd3fc;">📅 만료일: {date_formatted} (D-{diff_days}일)</span>'
            else:
                badge_html += f'<span style="font-size:0.80rem; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-weight:600; border:1px solid #fca5a5;">⚠️ 만료됨 ({date_formatted})</span>'
        badge_html += '</div>'
        return badge_html

    @classmethod
    def get_display_product_name(cls) -> str:
        """보유 라이선스 상태에 맞춰 화면에 노출될 통합 제품명을 동적으로 구성합니다."""
        active = cls.get_active_products()
        
        prods = []
        if "CafeCrawler" in active:
            prods.append("카페 수집기 Pro")
        if "EventStats" in active:
            prods.append("이벤트 활동 분석기")
        if "AutoComment" in active:
            prods.append("자동댓글러")

        if not prods:
            return "카페 몬스터 통합 체험판"
        elif len(prods) == 3:
            return "카페 몬스터 통합본 Pro"
        else:
            return f"카페 몬스터 [{' + '.join(prods)}]"

    # --- 체험판 사용량 (trial_logs) 연동 기능 ---
    @classmethod
    def get_trial_used_count(cls, product_id: str) -> int:
        """체험판 누적 사용량을 서버(Supabase) 및 로컬 AppData에서 대조 및 동기화하여 가져옵니다."""
        hwid = cls.get_hwid()
        local_count = 0
        try:
            if os.path.exists(TRIAL_SETTINGS_FILE):
                with open(TRIAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    local_count = data.get(product_id, 0)
        except Exception:
            pass

        server_count = 0
        try:
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/trial_logs?hwid=eq.{hwid}&product_id=eq.{product_id}&select=used_count"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            res = requests.get(url, headers=headers, timeout=0.5)
            if res.status_code == 200:
                res_data = res.json()
                if res_data:
                    server_count = res_data[0].get("used_count", 0)
                else:
                    # 서버에 매칭되는 HWID 체험 이력이 전혀 없다면 로컬 카운트도 0으로 리셋
                    local_count = 0
        except Exception:
            pass

        true_count = max(local_count, server_count)
        cls.save_trial_used_count(product_id, true_count)
        return true_count

    @classmethod
    def save_trial_used_count(cls, product_id: str, count: int):
        """로컬 AppData 및 Supabase trial_logs 서버 테이블에 체험 수집 누적 카운트를 저장합니다."""
        # 1. 로컬 저장
        data = {}
        try:
            if os.path.exists(TRIAL_SETTINGS_FILE):
                with open(TRIAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            pass
        
        data[product_id] = count
        try:
            os.makedirs(os.path.dirname(TRIAL_SETTINGS_FILE), exist_ok=True)
            with open(TRIAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 2. Supabase trial_logs 테이블 저장
        try:
            hwid = cls.get_hwid()
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/trial_logs?on_conflict=hwid,product_id"
            payload = {
                "hwid": hwid,
                "product_id": product_id,
                "used_count": count,
                "updated_at": datetime.datetime.utcnow().isoformat()
            }
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            requests.post(url, headers=headers, json=payload, timeout=0.5)
        except Exception:
            pass

    @classmethod
    def validate_and_bind_key(cls, key: str) -> tuple[bool, str]:
        """시리얼 키의 유효성을 검사하고, 이 기기(HWID)에 바인딩 및 저장합니다."""
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        url_key = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?serial_key=eq.{key}&select=product_id,status,bound_value"
        try:
            res_key = requests.get(url_key, headers=headers, timeout=1.0)
            if res_key.status_code != 200:
                return False, f"서버 오류 (HTTP {res_key.status_code})"
            
            key_data = res_key.json()
            if not key_data:
                return False, "유효하지 않은 라이선스 키입니다."
            
            item = key_data[0]
            prod_id = item.get("product_id")
            status = item.get("status")
            bound = item.get("bound_value")
            hwid = cls.get_hwid()
            
            if status == "active" and bound and bound != hwid:
                return False, "이미 다른 기기에 등록된 라이선스 키입니다."
            
            if prod_id:
                auth_prod = MonsterAuth(
                    product_id=prod_id,
                    license_key=key,
                    supabase_url=SUPABASE_URL,
                    supabase_key=SUPABASE_KEY
                )
                success, msg, col_limit = auth_prod.verify_license()
                if success:
                    cls.save_key(key)
                    cls.clear_cache()
                    cls.get_active_products()
                    return True, "라이선스 인증에 성공하였습니다!"
                else:
                    return False, f"인증 실패: {msg}"
            return False, "알 수 없는 제품 코드입니다."
        except Exception as e:
            return False, f"서버 연결 오류: {e}"

    @classmethod
    def check_license_status(cls, target_product_id: str = None) -> bool:
        """현재 실행 중인 에디션(target_product_id)의 유효 라이선스가 바인딩되어 있는지 확인합니다."""
        if not target_product_id:
            target_product_id = cls.get_current_product_id()
        active = cls.get_active_products()
        return target_product_id in active

    @classmethod
    def start_trial(cls) -> tuple[bool, str]:
        """무료 체험판 시작 시 각 제품의 trial_logs를 Supabase에 초기 등록합니다."""
        hwid = cls.get_hwid()
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates"
        }
        products = ["CafeCrawler", "EventStats", "AutoComment"]
        try:
            for prod in products:
                url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/trial_logs"
                payload = {"hwid": hwid, "product_id": prod, "used_count": 0}
                requests.post(url, headers=headers, json=payload, timeout=1.0)
            return True, "무료 체험판 세션이 시작되었습니다."
        except Exception as e:
            return True, f"오프라인 체험판으로 시작합니다."

    # --- 로컬 캐시 관리 헬퍼 ---
    @classmethod
    def _read_local_cache(cls) -> dict | None:
        cache_path = cls.get_cache_file_path()
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 유효 기한 30일 체크 (1회 인증 후 30일간 자동 통과)
            updated_at = cache.get("updated_at", 0)
            if time.time() - updated_at > 30 * 24 * 3600:
                return None
            # 신규 스키마 검증 (exp_dates 필수: 이전 구버전 캐시 무효화 및 서버 재조회 유도)
            if "exp_dates" not in cache or "license_types" not in cache:
                return None
            return cache
        except Exception:
            return None

    @classmethod
    def _write_local_cache(cls, products: set[str], limits: dict):
        try:
            cache = {
                "products": list(products),
                "limits": limits,
                "exp_dates": cls._cached_exp_dates,
                "license_types": cls._cached_license_types,
                "updated_at": time.time()
            }
            cache_path = cls.get_cache_file_path()
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
