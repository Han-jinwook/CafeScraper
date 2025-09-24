# 네이버 카페 스크래퍼 프로젝트 계획서

## 📋 프로젝트 개요
- **목표**: 네이버 카페 게시글/댓글/이미지를 CSV로 수집하여 GPT 브레인으로 활용
- **대상**: 본인 운영 카페만 (치유일기, 상담글 등)
- **출력**: CSV (한 게시글당 1행, 이미지는 Base64로 임베드)

## 🏗️ 아키텍처
```
CafeScraper/
├── app/
│   ├── main.py              # FastAPI 서버
│   ├── scraper/
│   │   └── naver.py         # 네이버 스크래퍼 핵심 로직
│   └── utils/
│       └── csv_writer.py    # CSV 저장 유틸
├── sessions/                # 쿠키/세션 저장
├── outputs/                 # CSV 결과물
├── snapshots/              # 디버깅용 스크린샷
├── test_login.py           # 로그인 테스트
└── requirements.txt        # 의존성
```

## 📊 데이터 스키마 (CSV)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| cafe_id | string | 카페 ID |
| article_id | string | 게시글 ID |
| article_url | string | 게시글 URL |
| title | string | 제목 |
| author_nickname | string | 작성자 |
| posted_at | ISO8601 | 작성일시 |
| content_text | string | 본문(텍스트) |
| content_html | string | 본문(HTML) |
| images_base64_json | JSON | 이미지 배열(Base64) |
| comments_json | JSON | 댓글 배열 |
| scraped_at | ISO8601 | 수집일시 |

## 🎯 핵심 기능 요구사항
1. **수동 로그인**: 브라우저에서 직접 로그인 → 쿠키 저장/복원
2. **게시글 수집**: 제목, 내용, 메타데이터
3. **댓글 필터링**: 특정 닉네임만 포함/제외
4. **이미지 처리**: Base64로 변환하여 CSV에 임베드
5. **CSV 저장**: 한 게시글당 1행, JSON 칼럼으로 구조화

## 📅 개발 단계별 계획

### ✅ Phase 1: 기본 구조 (완료)
- [x] FastAPI + Playwright 프로젝트 초기화
- [x] CSV 스키마 설계
- [x] 수동 로그인 + 쿠키 저장 구현
- [x] 기본 API 엔드포인트 구성
- [x] 테스트 스크립트 작성

### 🔄 Phase 2: 핵심 스크래핑 (진행중)
- [ ] 게시글 상세 정보 수집 (제목, 내용, 작성자, 날짜)
- [ ] 이미지 수집 및 Base64 변환
- [ ] 댓글 수집 및 닉네임 필터링
- [ ] CSV 저장 로직 완성

### ⏳ Phase 3: 안정화
- [ ] 에러 처리 및 재시도 로직
- [ ] 속도 제한 및 안티봇 대응
- [ ] 배치 처리 (여러 게시글)
- [ ] 로깅 및 모니터링

### ⏳ Phase 4: UI/UX
- [ ] 간단한 웹 인터페이스
- [ ] 진행상황 표시
- [ ] 결과 다운로드

## 🚨 현재 상태 (2025-01-23)
- **완료**: 프로젝트 구조, 로그인 기능, API 기본 틀
- **진행중**: 게시글 스크래핑 로직 구현
- **다음**: 네이버 카페 DOM 구조 분석 및 파싱 로직

## 🔧 기술 스택
- **Backend**: Python + FastAPI
- **Browser**: Playwright (Chromium)
- **Storage**: CSV + 로컬 파일시스템
- **Auth**: 쿠키 기반 세션 관리

## 📝 개발 노트
- 네이버 카페는 동적 로딩이 많아 `wait_for_load_state("networkidle")` 필수
- 안티봇 탐지 회피를 위해 실제 브라우저 사용 (headless=False)
- 이미지 리사이즈 고려 (기본 1280px, 품질 85%)
- 댓글 페이지네이션 처리 필요

## 🎯 다음 작업
1. 네이버 카페 게시글 DOM 구조 분석
2. 제목/내용/작성자/날짜 추출 로직 구현
3. 이미지 URL 수집 및 Base64 변환
4. 댓글 수집 및 필터링 로직

---
*마지막 업데이트: 2025-01-23*
*다음 세션에서 이어서 작업할 때 이 파일을 먼저 확인하세요.*
