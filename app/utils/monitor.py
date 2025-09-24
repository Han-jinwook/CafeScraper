"""
모니터링 시스템 - 성능 메트릭 수집 및 알림
"""

import time
import psutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class PerformanceMetrics:
    """성능 메트릭 데이터 클래스"""
    timestamp: str
    operation: str
    duration: float
    memory_usage_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class ScrapingStats:
    """스크래핑 통계 데이터 클래스"""
    total_articles: int
    successful_articles: int
    failed_articles: int
    total_duration: float
    average_duration_per_article: float
    memory_peak_mb: float
    start_time: str
    end_time: str

class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self, metrics_dir: str = "metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)
        
        self.current_session = None
        self.session_start_time = None
        self.session_metrics = []
        
    def start_session(self, operation: str) -> str:
        """새로운 모니터링 세션 시작"""
        self.current_session = f"{operation}_{int(time.time())}"
        self.session_start_time = time.time()
        self.session_metrics = []
        return self.current_session
    
    def record_metric(self, operation: str, duration: float, success: bool, error_message: str = None) -> None:
        """성능 메트릭 기록"""
        if not self.current_session:
            return
            
        # 시스템 리소스 정보 수집
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()
        
        metric = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            duration=duration,
            memory_usage_mb=memory_info.used / (1024 * 1024),
            cpu_percent=cpu_percent,
            success=success,
            error_message=error_message
        )
        
        self.session_metrics.append(metric)
        
        # 실시간 메트릭 저장
        self._save_realtime_metric(metric)
    
    def end_session(self) -> ScrapingStats:
        """세션 종료 및 통계 생성"""
        if not self.current_session or not self.session_metrics:
            return None
            
        end_time = time.time()
        total_duration = end_time - self.session_start_time
        
        # 통계 계산
        successful_metrics = [m for m in self.session_metrics if m.success]
        failed_metrics = [m for m in self.session_metrics if not m.success]
        
        memory_peak = max(m.memory_usage_mb for m in self.session_metrics) if self.session_metrics else 0
        avg_duration = sum(m.duration for m in successful_metrics) / len(successful_metrics) if successful_metrics else 0
        
        stats = ScrapingStats(
            total_articles=len(self.session_metrics),
            successful_articles=len(successful_metrics),
            failed_articles=len(failed_metrics),
            total_duration=total_duration,
            average_duration_per_article=avg_duration,
            memory_peak_mb=memory_peak,
            start_time=datetime.fromtimestamp(self.session_start_time).isoformat(),
            end_time=datetime.fromtimestamp(end_time).isoformat()
        )
        
        # 세션 통계 저장
        self._save_session_stats(stats)
        
        # 세션 초기화
        self.current_session = None
        self.session_start_time = None
        self.session_metrics = []
        
        return stats
    
    def _save_realtime_metric(self, metric: PerformanceMetrics) -> None:
        """실시간 메트릭 저장"""
        today = datetime.now().strftime("%Y-%m-%d")
        metrics_file = self.metrics_dir / f"realtime_{today}.jsonl"
        
        with open(metrics_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(metric), ensure_ascii=False) + "\n")
    
    def _save_session_stats(self, stats: ScrapingStats) -> None:
        """세션 통계 저장"""
        today = datetime.now().strftime("%Y-%m-%d")
        stats_file = self.metrics_dir / f"sessions_{today}.jsonl"
        
        with open(stats_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(stats), ensure_ascii=False) + "\n")
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """일일 통계 조회"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        stats_file = self.metrics_dir / f"sessions_{date}.jsonl"
        
        if not stats_file.exists():
            return {"error": "해당 날짜의 통계가 없습니다."}
        
        sessions = []
        with open(stats_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    sessions.append(json.loads(line))
        
        if not sessions:
            return {"error": "통계 데이터가 없습니다."}
        
        # 통계 집계
        total_sessions = len(sessions)
        total_articles = sum(s["total_articles"] for s in sessions)
        total_successful = sum(s["successful_articles"] for s in sessions)
        total_failed = sum(s["failed_articles"] for s in sessions)
        total_duration = sum(s["total_duration"] for s in sessions)
        avg_memory_peak = sum(s["memory_peak_mb"] for s in sessions) / total_sessions
        
        return {
            "date": date,
            "total_sessions": total_sessions,
            "total_articles": total_articles,
            "successful_articles": total_successful,
            "failed_articles": total_failed,
            "success_rate": (total_successful / total_articles * 100) if total_articles > 0 else 0,
            "total_duration_hours": total_duration / 3600,
            "average_memory_peak_mb": avg_memory_peak,
            "sessions": sessions
        }
    
    def get_system_status(self) -> Dict:
        """시스템 상태 조회"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": psutil.cpu_percent(),
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": (disk.used / disk.total) * 100
            }
        }
    
    def cleanup_old_metrics(self, days: int = 30) -> None:
        """오래된 메트릭 파일 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for file_path in self.metrics_dir.glob("*.jsonl"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                file_path.unlink()
                print(f"삭제된 오래된 메트릭 파일: {file_path}")

# 전역 모니터 인스턴스
performance_monitor = PerformanceMonitor()
