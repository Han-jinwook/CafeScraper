@echo off
echo 🏠 집에서 작업 환경 설정 중...

REM Python 경로 설정
set PYTHONPATH=D:\CafeScraper

REM 가상환경 활성화
call .venv\Scripts\activate.bat

REM 서버 실행
echo 🚀 서버 시작 중...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
