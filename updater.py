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
    PRODUCT_ID = "CafeCrawler"
    
    @classmethod
    def check_for_updates(cls):
        try:
            logger.info("🔍 [라이브러리 검증] 최신 버전 확인 중...")
            
            update_info = CommonUpdater.check_for_updates(
                product_id=cls.PRODUCT_ID,
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
            
            extracted_folder = None
            extracted_exe_name = None
            
            if not os.path.isabs(update_package_path):
                update_package_path = os.path.join(app_dir, update_package_path)
            
            if update_package_path.endswith('.zip'):
                import zipfile
                logger.info("📦 압축 해제 중...")
                with zipfile.ZipFile(update_package_path, 'r') as zip_ref:
                    top_levels = set([name.split('/')[0] for name in zip_ref.namelist() if '/' in name])
                    if top_levels:
                        extracted_folder = list(top_levels)[0]
                        extracted_exe_name = "CafeScraper.exe"
                    
                    zip_ref.extractall(app_dir)
                os.remove(update_package_path)
            
            if not extracted_folder:
                logger.error("업데이트 패키지 내 구조를 분석할 수 없습니다.")
                return False
            
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
taskkill /f /im "{os.path.basename(current_exe)}" > nul 2>&1
taskkill /f /im "CafeScraper.exe" > nul 2>&1
timeout /t 1 /nobreak > nul

if exist "{app_dir}\\_internal" rmdir /s /q "{app_dir}\\_internal"
xcopy /E /Y /C /Q "{os.path.join(app_dir, extracted_folder, '*')}" "{app_dir}\\"
rmdir /s /q "{os.path.join(app_dir, extracted_folder)}"
start "" "{os.path.join(app_dir, extracted_exe_name)}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="cp949") as f:
                f.write(bat_content)
                
            logger.info("🔄 업데이트 헬퍼 생성 완료. 프로세스를 종료하고 업데이트를 적용합니다.")
            subprocess.Popen([bat_path], shell=True)
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"업데이트 적용 중 오류 발생: {e}")
            return False
