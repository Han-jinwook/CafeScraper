# 🔱 Monster 공통 라이브러리 - exporter.py
# - 버전: v1.0
# - 갱신 일시: 2026-06-03
# - 관리 주체: Monster 총괄 AI (Hub AI)

import os
import sys
import datetime
import subprocess

class MonsterExporter:
    """
    [3Monster Master Library] 공통 데이터 내보내기 및 다운로드 경로 표준화 헬퍼 모듈
    모든 데이터의 저장 위치를 사용자 다운로드 폴더로 일원화하고, 
    중복 저장을 예방하기 위한 MMDD_HHMM 단축형 타임스탬프 파일명 생성을 지원합니다.
    """

    @staticmethod
    def get_download_path():
        """사용자 OS에 최적화된 다운로드(Downloads) 폴더 경로를 반환합니다."""
        # Windows의 일반적인 홈디렉토리 감지 우선 적용
        if sys.platform == "win32":
            # OneDrive나 기타 동기화 폴더 설정을 감안하여 레지스트리 경로 조회를 시도할 수 있으나,
            # 가장 범용적인 USERPROFILE 기반 Downloads 경로를 기본 사용합니다.
            user_profile = os.environ.get("USERPROFILE")
            if user_profile:
                download_dir = os.path.join(user_profile, "Downloads")
                if os.path.exists(download_dir):
                    return download_dir
        
        # macOS 및 Linux, 또는 fallback 처리
        return os.path.join(os.path.expanduser('~'), 'Downloads')

    @classmethod
    def generate_filename(cls, prefix, extension="xlsx"):
        """
        [강령 준수] 표준 파일명 생성기
        - 포맷: [식별자]_[MMDD_HHMM].[확장자]
        - 예: nplace.naver.com_0603_1426.xlsx
        """
        timestamp = datetime.datetime.now().strftime("%m%d_%H%M")
        # 파일명에 사용할 수 없는 특수문자 제거 정제 작업
        safe_prefix = prefix
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            safe_prefix = safe_prefix.replace(char, '_')
            
        # 확장자의 앞자리 점(.) 제거 대응
        clean_ext = extension.lstrip('.')
        
        return f"{safe_prefix}_{timestamp}.{clean_ext}"

    @classmethod
    def get_export_filepath(cls, prefix, extension="xlsx"):
        """
        일원화된 다운로드 폴더 내의 최종 파일 저장 경로(절대경로)를 생성합니다.
        """
        download_dir = cls.get_download_path()
        filename = cls.generate_filename(prefix, extension)
        return os.path.join(download_dir, filename)

    @staticmethod
    def open_in_explorer(filepath):
        """
        저장이 완료된 후, 해당 파일이 위치한 다운로드 폴더를 열고 
        해당 파일을 윈도우 탐색기 상에서 포커싱/하이라이트합니다.
        """
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            return False
            
        try:
            if sys.platform == "win32":
                # 파일 포커싱을 준수하여 탐색기 실행
                subprocess.Popen(f'explorer /select,"{abs_path}"', shell=True)
                return True
            elif sys.platform == "darwin":
                # macOS Finder에서 파일 하이라이트
                subprocess.Popen(["open", "-R", abs_path])
                return True
            else:
                # Linux 및 기타 OS
                subprocess.Popen(["xdg-open", os.path.dirname(abs_path)])
                return True
        except Exception:
            return False
