# 🔱 Monster 공통 라이브러리 - logger.py
# - 버전: v1.0
# - 갱신 일시: 2026-05-18
# - 관리 주체: Monster 총괄 AI (Hub AI)

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import traceback
import subprocess
import hashlib
import uuid

class MonsterLogger:
    """
    [3Monster Master Library] 공통 로깅 및 디버깅 헬퍼 모듈
    app_debug.log를 최대 5MB 크기로 롤링 생성하며, 
    오류 정보를 원클릭 복사 가능한 표준 양식으로 빌드하는 기능을 제공합니다.
    """
    
    def __init__(self, product_id, log_file="app_debug.log"):
        self.product_id = product_id
        self.log_file = log_file
        self.logger = logging.getLogger(f"MonsterLogger_{product_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # 중복 핸들러 방지
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        """회전 로깅 핸들러(최대 5MB, 3개 백업) 및 콘솔 출력을 바인딩합니다."""
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        # 1. 파일 핸들러 (5MB 용량 제한 강제화 - 강령 준수)
        try:
            file_handler = RotatingFileHandler(
                self.log_file, 
                maxBytes=5 * 1024 * 1024, 
                backupCount=3, 
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception:
            pass  # 권한 등 파일 생성이 불가능한 경우 우회

        # 2. 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def _get_hwid(self):
        """표준 HWID 계산"""
        try:
            if sys.platform == "win32":
                output = subprocess.check_output(
                    'wmic csproduct get uuid', 
                    shell=True, 
                    stderr=subprocess.DEVNULL
                ).decode().split('\n')[1].strip()
                if output and "UUID" not in output:
                    return hashlib.sha256(output.encode('utf-8')).hexdigest()
        except Exception:
            pass
        node = uuid.getnode()
        return hashlib.sha256(str(node).encode('utf-8')).hexdigest()

    def get_clipboard_error_text(self, exception):
        """
        고객센터 문의 시 즉시 붙여넣을 수 있도록 
        오류 정보, HWID, traceback을 규격화된 문자열로 생성합니다.
        """
        tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        hwid = self._get_hwid()
        
        err_msg = [
            "=================== [3Monster Error Report] ===================",
            f"대상 제품(Product): {self.product_id}",
            f"기기 식별(HWID): {hwid}",
            f"발생 일시(Time): {os.popen('date /t').read().strip() if sys.platform == 'win32' else 'N/A'}",
            f"오류 유형(Error Type): {type(exception).__name__}",
            f"오류 내용(Message): {str(exception)}",
            "------------------- [Traceback Detail] -------------------",
            tb_str,
            "=============================================================="
        ]
        return "\n".join(err_msg)
