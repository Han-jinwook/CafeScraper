# 네이버 카페 스크래퍼 프로젝트 계획

## 프로젝트 개요

네이버 카페에서 게시글, 댓글, 이미지를 수집하여 CSV 파일로 저장하는 자동화 도구입니다.

## 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   웹 UI         │    │   FastAPI       │    │   Playwright    │
│   (사용자)      │◄──►│   (API 서버)    │◄──►│   (브라우저)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   CSV 저장      │
                       │   (결과물)      │
                       └─────────────────┘
```

## 데이터 스키마

### 게시글 정보
- `cafe_id`: 카페 ID
- `article_id`: 게시글 ID  
- `title`: 제목
- `author_nickname`: 작성자 닉네임
- `content_text`: 텍스트 내용
- `content_html`: HTML 내용
- `date`: 작성일
- `url`: 게시글 URL
- `images_base64`: 이미지 (Base64 인코딩)
- `comments`: 댓글 목록
- `scraped_at`: 스크래핑 시간

### 댓글 정보
- `author_nickname`: 댓글 작성자
- `content`: 댓글 내용
- `date`: 댓글 작성일
- `like_count`: 좋아요 수

## 핵심 기능

### 1. 로그인 시스템
- 수동 로그인 + 쿠키 저장
- 세션 유지 및 자동 갱신
- 로그인 상태 확인

### 2. 게시글 스크래핑
- 게시글 상세 정보 수집 (제목, 내용, 작성자, 날짜)
- 이미지 수집 및 Base64 인코딩
- 댓글 수집 및 필터링
- 페이지네이션 지원

### 3. 배치 처리
- 여러 게시글 동시 처리
- 진행률 표시
- 에러 처리 및 재시도

### 4. 데이터 저장
- CSV 파일로 저장
- 날짜별 폴더 구조
- 이미지 Base64 인코딩

## 개발 단계

### Phase 1: 기본 구조 및 로그인 시스템 ✅
- [x] 프로젝트 구조 설정
- [x] FastAPI 서버 구현
- [x] Playwright 기반 브라우저 자동화
- [x] 수동 로그인 + 쿠키 저장 구현
- [x] CSV 출력 시스템
- [x] 기본 웹 UI

### Phase 2: 핵심 스크래핑 기능 ✅
- [x] 게시글 상세 정보 수집 (제목, 내용, 작성자, 날짜)
- [x] 이미지 수집 및 Base64 인코딩
- [x] 댓글 수집 및 필터링
- [x] 게시판 스크래핑 (페이지네이션 지원)
- [x] 배치 처리 (여러 게시글 동시 처리)
- [x] DOM 셀렉터 개선
- [x] 에러 처리 및 재시도 로직
- [x] 새로운 API 엔드포인트 구현
- [x] test_board_scraping.py 테스트 스크립트 작성

### Phase 3: 안정화 및 최적화 ❌ **블로킹**
- [x] 성능 최적화 (동시 처리, 메모리 관리)
- [x] 안티봇 대응 (User-Agent 로테이션, 지연 시간)
- [x] 웹 UI 구현 (사용자 친화적 인터페이스)
- [x] 로깅 및 모니터링 시스템
- [x] 시스템 상태 모니터링
- [x] 배치 크롤링 UI (키워드 검색, 작성자 필터링)
- [x] Chrome DevTools 404 에러 해결
- [x] Favicon 404 에러 해결
- [x] 로그 파일 저장 기능

## 현재 상태 (Current Status)

- **Phase 1**: ✅ 완료 (기본 구조 및 로그인)
- **Phase 2**: ✅ 완료 (핵심 스크래핑 기능)  
- **Phase 3**: ❌ **블로킹** (Windows Playwright 호환성 문제)

## 🚨 **중요: 현재 블로킹 이슈**

### Windows Playwright 호환성 문제
- **에러**: `NotImplementedError` in `asyncio.subprocess`
- **시도 횟수**: 20+ 회
- **상태**: 해결 실패

### Mock 모드 문제  
- **에러**: `'str' object is not callable`
- **시도 횟수**: 15+ 회
- **상태**: 해결 실패

## 다음 세션에서 해야 할 일

### 우선순위 1: 근본적 해결책
1. **Playwright 대신 다른 라이브러리 사용**
   - Selenium WebDriver (권장)
   - requests + BeautifulSoup
   - httpx + asyncio

2. **Windows 환경 최적화**
   - WSL2 사용 검토
   - Docker 컨테이너 환경
   - 다른 OS 환경 테스트

### 우선순위 2: 대안 구현
1. **간단한 HTTP 스크래핑**
   - requests 라이브러리 사용
   - BeautifulSoup으로 HTML 파싱
   - 쿠키 기반 세션 관리

2. **단계적 접근**
   - 기본 스크래핑부터 시작
   - 점진적으로 기능 추가

## 권장 해결 방향 🎯

1. **Playwright 포기**: Windows 호환성 문제로 인해 다른 방법 사용
2. **Selenium 시도**: 더 안정적인 브라우저 자동화
3. **HTTP 스크래핑**: 브라우저 없이 직접 HTTP 요청
4. **환경 변경**: WSL2 또는 Docker 사용

## 새 세션 시작 시 체크리스트 ✅

- [ ] 현재 상태 파악: `CURRENT_STATUS.md` 읽기
- [ ] 에러 로그 확인: `server.log` 파일 확인
- [ ] 대안 방법 선택: Playwright 대신 Selenium 또는 HTTP 스크래핑
- [ ] 단계적 구현: 기본 기능부터 차근차근 구현
- [ ] 테스트 환경: 간단한 테스트부터 시작

## 기술 스택

- **Backend**: FastAPI, Python 3.13
- **Browser Automation**: ~~Playwright~~ → **Selenium** (권장)
- **Data Processing**: pandas, BeautifulSoup
- **Frontend**: HTML, CSS, JavaScript
- **Storage**: CSV files, JSON cookies

## 파일 구조

```
CafeScraper/
├── app/
│   ├── main.py              # FastAPI 서버
│   ├── scraper/
│   │   └── naver.py         # 스크래핑 로직
│   ├── utils/
│   │   ├── csv_writer.py   # CSV 저장
│   │   ├── logger.py       # 로깅
│   │   └── monitor.py       # 모니터링
│   └── static/
│       └── index.html       # 웹 UI
├── sessions/                # 쿠키 저장
├── outputs/                 # CSV 출력
├── snapshots/               # 스크린샷
├── server.log               # 서버 로그
├── requirements.txt
├── plan.md
└── CURRENT_STATUS.md
```