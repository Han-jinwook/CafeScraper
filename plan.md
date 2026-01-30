# 네이버 카페 스크래퍼 프로젝트 계획
(업데이트: 2026-01-27 16:15)

## 프로젝트 개요

네이버 카페에서 게시글, 댓글, 이미지를 수집하여 CSV 및 Supabase DB에 저장하는 로컬 GUI 자동화 도구입니다.

## 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit UI  │    │   Python Logic  │    │    Selenium     │
│   (로컬 GUI)    │◄──►│   (Crawler)     │◄──►│   (Chrome)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
       ┌─────────────────┐             ┌─────────────────┐
       │   CSV 저장      │             │   Supabase DB   │
       │   (로컬 파일)   │             │   (Cloud)       │
       └─────────────────┘             └─────────────────┘
```

## 데이터 스키마 (Supabase)

### 1. cafe_posts (게시글)
- `id`: bigint (PK)
- `cafe_name`: text
- `keyword`: text
- `title`: text
- `content`: text
- `author`: text
- `date`: text
- `link`: text (Unique)
- `content_hash`: text (MD5)
- `vector_status`: boolean
- `created_at`: timestamptz

### 2. cafe_comments (댓글)
- `id`: bigint (PK)
- `post_id`: bigint (FK to cafe_posts.id)
- `content`: text
- `author`: text
- `date`: text
- `link`: text (원본 글 링크)
- `content_hash`: text (MD5)
- `created_at`: timestamptz

## 현재 개발 상태 ✅

### Phase 1: 환경 전환 및 GUI 구현 ✅
- [x] FastAPI/Playwright 서버 방식 포기 -> Streamlit/Selenium 로컬 방식으로 전환
- [x] Streamlit 기반 2단계(브라우저 열기 -> 크롤링 시작) UI 구현
- [x] 로컬 크롬 프로필 연동 및 수동 로그인 지원

### Phase 2: 스크래핑 로직 고도화 (진행 중) ⚠️
- [x] 최신 네이버 카페 SPA(React) 방식 대응
- [x] 공지사항/필독글 필터링 로직 강화
- [x] 게시글 ID 추출 로직 강화 (다양한 URL 패턴 대응)
- [x] 무한 로딩 및 차단 페이지(Sorry) 감지/우회 로직 추가

### Phase 3: 데이터 저장 및 연동 ✅
- [x] 로컬 CSV 저장 (날짜별 폴더)
- [x] Supabase DB 연동 (게시글 + 댓글 Upsert)
- [x] 게시글-댓글 관계형 저장 구현

## 🚨 현재 주요 블로킹 이슈

1. **네이버 차단(Sorry 페이지)**: 잦은 요청 시 "잠시 후 다시 확인해주세요" 페이지 노출.
2. **동적 요소 인식 불안정**: 게시판 목록에서 후보 링크는 발견되나, 게시글 정보를 최종 추출하는 단계에서 0개로 끝나는 현상 발생.
3. **세션 끊김**: 크롤링 도중 `invalid session id` 에러와 함께 브라우저 연결이 강제 종료되는 문제.

## 다음 세션 작업 방향

1. **추출 로직 정밀 교정**: `_extract_article_links_from_board` 메서드에서 발견된 링크들의 실제 DOM 구조를 다시 분석하여 데이터 매핑 성공률 제고.
2. **차단 우회 고도화**: 단순 대기 외에 마우스 움직임 모사, 스크롤 패턴 불규칙화 등 인간 행동 모사(Human Mimicry) 강화.
3. **에러 복구**: 세션 종료 시 자동으로 브라우저를 재시작하고 중단된 지점부터 이어가는 체크포인트 기능 검토.
