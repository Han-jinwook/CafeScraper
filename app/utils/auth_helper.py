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
    _hwid = None

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
        if not os.path.exists(LICENSE_FILE):
            return []
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []

    @classmethod
    def save_key(cls, key: str) -> bool:
        """새 라이선스 키를 로컬 파일에 추가 저장합니다."""
        try:
            keys = cls.load_saved_keys()
            if key not in keys:
                keys.append(key)
                os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
                with open(LICENSE_FILE, "w", encoding="utf-8") as f:
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
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
            except:
                pass

    @classmethod
    def get_active_products(cls) -> set[str]:
        """HWID에 바인딩된 활성 라이선스 및 저장된 키들을 검증하여 권한 셋을 반환합니다."""
        if cls._cached_active_products is not None:
            return cls._cached_active_products

        # 1. 로컬 캐시 조회
        local_cache = cls._read_local_cache()
        if local_cache is not None:
            cls._cached_active_products = set(local_cache.get("products", []))
            cls._cached_limits = local_cache.get("limits", {})
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

        # 2.1 HWID에 바인딩된 활성 라이선스들 조회 (REST API 0.5초 타임아웃 제한)
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?bound_value=eq.{hwid}&status=eq.active&select=product_id,expire_date,collection_limit,serial_key,first_run_date"
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
                    # 만료일 체크
                    if exp:
                        try:
                            exp_clean = exp.replace('Z', '+00:00')
                            exp_dt = datetime.datetime.fromisoformat(exp_clean)
                            if exp_dt.timestamp() < datetime.datetime.now(datetime.timezone.utc).timestamp():
                                continue
                        except Exception:
                            pass
                    if prod:
                        active_prods.add(prod)
                        limits[prod] = limit
                        
                        # 실행일자(first_run_date) 누락 시 백필 수행
                        if not first_run and key:
                            try:
                                from 라이브러리.auth import MonsterAuth
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

        # 2.2 저장된 키들 유효성 검사 및 바인딩 시도
        saved_keys = cls.load_saved_keys()
        for key in saved_keys:
            try:
                # 저장된 키가 어떤 product_id 용인지 먼저 조회
                url_key = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?serial_key=eq.{key}&select=product_id"
                res_key = requests.get(url_key, headers=headers, timeout=3.0)
                if res_key.status_code == 200:
                    key_data = res_key.json()
                    if key_data:
                        prod_id = key_data[0].get("product_id")
                        if prod_id and prod_id not in active_prods:
                            # 해당 제품 ID로 바인딩 및 인증 수행
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
    def check_license_status(cls) -> bool:
        """현재 HWID에 바인딩된 유효 라이선스가 1개라도 존재하는지 확인합니다.
        캐시가 유효한 경우 캐시를 사용하여 즉시 반환합니다 (창 자동 닫기용)."""
        # 캐시를 지우지 않고 기존 캐시를 먼저 활용하여 빠르게 통과시킴
        # (validate_and_bind_key 호출 시 캐시가 갱신되므로 안전)
        active = cls.get_active_products()
        return len(active) > 0

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
        if not os.path.exists(CACHE_FILE):
            return None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 유효 기한 30일 체크 (1회 인증 후 30일간 자동 통과)
            updated_at = cache.get("updated_at", 0)
            if time.time() - updated_at > 30 * 24 * 3600:
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
                "updated_at": time.time()
            }
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
