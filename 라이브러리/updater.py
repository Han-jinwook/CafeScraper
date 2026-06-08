# 🔱 Monster 공통 라이브러리 - updater.py
# - 버전: v1.1
# - 갱신 일시: 2026-05-18
# - 관리 주체: Monster 총괄 AI (Hub AI)

import os
import requests
import logging

logger = logging.getLogger(__name__)

class MonsterUpdater:
    """
    [3Monster Master Library] 표준 자동 업데이트 엔진
    Supabase REST API를 직접 조회하여 개별 앱의 신규 버전을 감지하고 다운로드합니다.
    """
    
    VERSION = "1.1.0"
    
    @classmethod
    def check_for_updates(cls, product_id, current_version, supabase_url=None, supabase_key=None):
        """서버에서 최신 버전을 확인하고 업데이트 정보 딕셔너리를 반환합니다."""
        url_base = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_KEY")
        
        if not url_base or not key:
            logger.error("업데이트 체크 실패: Supabase 설정 정보 누락")
            return None

        # 버전 역정렬 후 상위 1개만 조회하는 PostgREST API 쿼리
        url = f"{url_base.rstrip('/')}/rest/v1/app_versions?product_id=eq.{product_id}&order=version.desc&limit=1"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        try:
            # 0.5초 타임아웃 강제화
            response = requests.get(url, headers=headers, timeout=0.5)
            response.raise_for_status()
            data = response.json()

            if data:
                latest = data[0]
                if cls._is_newer(latest['version'], current_version):
                    return {
                        "version": latest['version'],
                        "download_url": latest['download_url'],
                        "release_notes": latest.get('release_notes', '')
                    }
            return None
        except requests.exceptions.Timeout:
            logger.warning("업데이트 체크 시간 초과 (0.5초 제한)")
            return None
        except Exception as e:
            logger.error(f"업데이트 체크 중 예외 발생: {e}")
            return None

    @staticmethod
    def _is_newer(latest, current):
        """버전 문자열(예: '1.2.3')의 크기를 비교합니다."""
        try:
            return [int(p) for p in latest.split('.')] > [int(p) for p in current.split('.')]
        except Exception:
            return latest > current

    @classmethod
    def download_to(cls, download_url, save_path):
        """파일 다운로드 엔진 (대용량 패키지 스트리밍 다운로드 지원)"""
        try:
            response = requests.get(download_url, stream=True, timeout=10.0) # 실제 파일 다운로드는 0.5초 이상 소요되므로 10초 예외 허용
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"공통 다운로드 패치 실패: {e}")
            return False
