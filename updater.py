import os
import sys
import logging
import subprocess
import requests
from app.utils.auth_helper import SUPABASE_URL, SUPABASE_KEY
from app.utils.app_version import read_app_version
from 라이브러리.updater import MonsterUpdater as CommonUpdater

logger = logging.getLogger(__name__)

class MonsterUpdater:
    """
    [3Monster] 표준 자동 업데이트 엔진 (공통 라이브러리 연동 브릿지 버전)
    """
    
    CURRENT_VERSION = read_app_version()
    
    @classmethod
    def _get_product_id(cls):
        try:
            app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            mode_path = os.path.join(app_dir, "mode.txt")
            if os.path.exists(mode_path):
                with open(mode_path, "r", encoding="utf-8") as f:
                    content = f.read().strip().upper()
                    if content.startswith('\ufeff'):
                        content = content[1:]
                    if content == "PRO_CAFECRAWLER": return "CafeCrawler"
                    if content == "PRO_EVENTSTATS": return "EventStats"
                    if content == "PRO_AUTOCOMMENT": return "AutoComment"
        except Exception:
            pass
        return "CafeCrawler"

    @classmethod
    def check_for_updates(cls):
        try:
            logger.info("🔍 [라이브러리 검증] 최신 버전 확인 중...")
            
            update_info = CommonUpdater.check_for_updates(
                product_id=cls._get_product_id(),
                current_version=cls.CURRENT_VERSION,
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY
            )
            
            if update_info:
                logger.info(f"🚀 새 업데이트 발견: {cls.CURRENT_VERSION} -> {update_info['version']}")
                return update_info
            else:
                logger.info("✅ 최신 버전을 사용 중입니다.")
                return None
                
        except Exception as e:
            logger.error(f"업데이트 확인 중 오류 발생: {e}")
            return None

    @classmethod
    def download_update(cls, download_url, target_filename="cafescraper_update.zip"):
        try:
            app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            
            if not os.path.isabs(target_filename):
                target_filename = os.path.join(app_dir, target_filename)

            logger.info(f"📥 업데이트 다운로드 시작: {download_url} -> {target_filename}")
            success = CommonUpdater.download_to(download_url, target_filename)
            if success:
                logger.info(f"✅ 다운로드 완료: {target_filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"다운로드 중 오류 발생: {e}")
            return False

    @classmethod
    def apply_update_and_restart(cls, update_package_path="cafescraper_update.zip"):
        try:
            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)
            bat_path = os.path.join(app_dir, "monster_update_helper.bat")
            
            if not os.path.isabs(update_package_path):
                update_package_path = os.path.join(app_dir, update_package_path)
            
            bat_content = f"""@echo off
taskkill /f /im "{os.path.basename(current_exe)}" > nul 2>&1
taskkill /f /im "CafeScraper.exe" > nul 2>&1
taskkill /f /im "CafeCrawler.exe" > nul 2>&1
taskkill /f /im "EventStats.exe" > nul 2>&1
taskkill /f /im "AutoComment.exe" > nul 2>&1
timeout /t 1 /nobreak > nul

if exist "{app_dir}\\_internal" rmdir /s /q "{app_dir}\\_internal"
tar -xf "{update_package_path}" -C "{app_dir}"
if exist "{update_package_path}" del "{update_package_path}" > nul 2>&1
start "" "{current_exe}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="cp949") as f:
                f.write(bat_content)
                
            logger.info("🔄 업데이트 헬퍼 생성 완료. 초고속 패치 적용 및 재시작...")
            subprocess.Popen([bat_path], shell=True)
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"업데이트 적용 중 오류 발생: {e}")
            return False
