"""
로깅 시스템 - 스크래핑 진행상황 및 에러 추적
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class ScrapingLogger:
    """스크래핑 전용 로거"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 로그 파일 설정
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"scraping_{today}.log"
        
        # 로거 설정
        self.logger = logging.getLogger("scraping")
        self.logger.setLevel(logging.INFO)
        
        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str) -> None:
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """에러 로그"""
        self.logger.error(message)
    
    def debug(self, message: str) -> None:
        """디버그 로그"""
        self.logger.debug(message)
    
    def log_scraping_start(self, url: str, total: int) -> None:
        """스크래핑 시작 로그"""
        self.info(f"🚀 스크래핑 시작: {url} (총 {total}개)")
    
    def log_scraping_progress(self, current: int, total: int, url: str) -> None:
        """스크래핑 진행 로그"""
        percentage = (current / total) * 100
        self.info(f"📄 [{current:3d}/{total:3d}] ({percentage:5.1f}%) {url}")
    
    def log_scraping_success(self, url: str, title: str) -> None:
        """스크래핑 성공 로그"""
        self.info(f"✅ 성공: {title} - {url}")
    
    def log_scraping_error(self, url: str, error: str) -> None:
        """스크래핑 에러 로그"""
        self.error(f"❌ 실패: {url} - {error}")
    
    def log_scraping_complete(self, successful: int, failed: int, total: int) -> None:
        """스크래핑 완료 로그"""
        self.info(f"📊 완료: 성공 {successful}개, 실패 {failed}개, 총 {total}개")
    
    def log_performance(self, operation: str, duration: float, details: str = "") -> None:
        """성능 로그"""
        self.info(f"⏱️ {operation}: {duration:.2f}초 {details}")
    
    def log_memory_usage(self, operation: str, memory_mb: float) -> None:
        """메모리 사용량 로그"""
        self.info(f"💾 {operation}: {memory_mb:.1f}MB")
    
    def log_antibot_measure(self, measure: str, details: str = "") -> None:
        """안티봇 대응 로그"""
        self.info(f"🛡️ 안티봇 대응: {measure} {details}")

# 전역 로거 인스턴스
scraping_logger = ScrapingLogger()
