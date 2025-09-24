# 네이버 카페 스크래퍼

네이버 카페의 게시글, 댓글, 이미지를 수집하여 CSV로 저장하는 도구입니다.

## 주요 기능

- 🔐 **수동 로그인**: 브라우저에서 직접 로그인하여 쿠키 저장
- 📝 **게시글 수집**: 제목, 내용, 작성자, 작성일시
- 💬 **댓글 필터링**: 특정 닉네임만 포함/제외 가능
- 🖼️ **이미지 처리**: Base64로 변환하여 CSV에 직접 저장
- 💾 **CSV 저장**: 한 게시글당 하나의 행으로 저장

## 설치 및 실행

### 1. 가상환경 생성 및 패키지 설치
```powershell
# 가상환경 생성
python -m venv .venv

# 가상환경 활성화
. .\.venv\Scripts\Activate.ps1

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install
```

### 2. 로그인 테스트
```powershell
python test_login.py
```

### 3. 서버 실행
```powershell
uvicorn app.main:app --reload
```

## 사용법

### 1. 로그인
- 브라우저가 열리면 네이버에 수동 로그인
- 로그인 완료 후 터미널에서 Enter 키 입력
- 쿠키가 `sessions/` 폴더에 저장됨

### 2. 게시글 스크래핑
- API 엔드포인트: `POST /scrape/article`
- 요청 예시:
```json
{
  "url": "https://cafe.naver.com/yourcafe/123456",
  "cafe_id": "yourcafe",
  "comment_filter": {
    "include": ["멀린", "큐레이터"],
    "exclude": ["관리자"]
  }
}
```

### 3. 결과 확인
- CSV 파일: `outputs/YYYY-MM-DD/articles_YYYYMMDD.csv`
- 스냅샷: `snapshots/` (디버깅용)

## CSV 구조

각 행은 하나의 게시글을 나타내며, 다음 필드를 포함합니다:

- `cafe_id`: 카페 ID
- `article_id`: 게시글 ID  
- `article_url`: 게시글 URL
- `title`: 제목
- `author_nickname`: 작성자 닉네임
- `posted_at`: 작성일시
- `content_text`: 본문 (텍스트)
- `content_html`: 본문 (HTML)
- `images_base64_json`: 이미지 배열 (Base64)
- `comments_json`: 댓글 배열
- `scraped_at`: 수집일시

## 주의사항

- 네이버 카페 이용약관을 준수하여 사용하세요
- 개인정보 보호에 주의하세요
- 과도한 요청은 차단될 수 있으니 적절한 간격을 두세요
- 본인 운영 카페만 대상으로 사용하세요

## 문제 해결

### 로그인 실패
- 브라우저에서 완전히 로그인했는지 확인
- 2FA가 설정된 경우 추가 인증 완료
- 쿠키 파일 삭제 후 재시도: `sessions/naver_cookies.json`

### 스크래핑 실패  
- 네트워크 연결 확인
- 카페 접근 권한 확인
- 스냅샷 파일 확인: `snapshots/` 폴더
