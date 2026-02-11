import runpy

# Streamlit 메인 페이지 라벨은 실행 파일명 기반이라
# 한글 메뉴명을 위해 app.py를 래핑 실행합니다.
runpy.run_path("app.py", run_name="__main__")
