"""PyInstaller 런타임 훅: Streamlit이 PyInstaller 환경에서 developmentMode=True로
잘못 판정하는 것을 방지합니다.

원인: Streamlit은 __file__ 경로에 'site-packages'가 없으면 개발모드로 인식.
PyInstaller 번들에서는 site-packages 경로가 없으므로 항상 개발모드가 됨.
"""
import os
import sys

if getattr(sys, "frozen", False):
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
