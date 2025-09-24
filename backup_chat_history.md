# 채팅 히스토리 백업 가이드

## 🔄 자동 동기화 방법

### 1. Cursor 설정
- `Ctrl + ,` → "Sync" 검색
- "Settings Sync" 활성화
- GitHub 계정 연결 확인

### 2. 프로젝트별 설정
- `.cursor-settings.json` 파일이 프로젝트에 포함됨
- 이 파일이 GitHub에 푸시되어 팀원과 공유됨

### 3. 수동 백업 (필요시)
```bash
# Cursor 채팅 히스토리 위치 (Windows)
%APPDATA%\Cursor\User\workspaceStorage\[프로젝트ID]\chat-history.json
```

## 🏠 집에서 작업 시

### 1. 프로젝트 클론
```bash
git clone https://github.com/Han-jinwook/CafeScraper.git
cd CafeScraper
```

### 2. 환경 설정
```bash
# Windows
setup_home.bat

# 또는 수동으로
set PYTHONPATH=D:\CafeScraper
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Cursor에서 프로젝트 열기
- Cursor에서 `File → Open Folder`
- `CafeScraper` 폴더 선택
- 자동으로 채팅 히스토리 동기화됨

## ⚠️ 주의사항

1. **GitHub 계정 연결 필수**: Cursor에서 GitHub 로그인 필요
2. **인터넷 연결**: 동기화를 위해 인터넷 연결 필요
3. **동일한 Cursor 버전**: 최신 버전 사용 권장

## 🔧 문제 해결

### 채팅 히스토리가 안 보일 때:
1. Cursor 재시작
2. GitHub 계정 재연결
3. 프로젝트 폴더 다시 열기

### 동기화가 안 될 때:
1. `Ctrl + Shift + P` → "Sync: Download Settings"
2. `Ctrl + Shift + P` → "Sync: Upload Settings"
3. Cursor 완전 종료 후 재시작
