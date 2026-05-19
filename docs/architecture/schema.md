# 로컬 SQLite DB 스키마

| 항목 | 값 |
|------|-----|
| **제목** | 로컬 SQLite DB 스키마 |
| **버전** | 1.3.23 (`version.txt`와 동기) |
| **일시** | 2026-05-18 |

코드 기준: `app/utils/sqlite_db.py`, `app/utils/event_db.py`, `pages/02_paper_collection.py` (`ensure_papers_schema`).  
스키마를 바꾼 뒤에는 이 문서의 **버전·일시**를 함께 갱신합니다.

---

## DB 파일 분리·경로

| 용도 | 기본 파일 | 환경 변수(우선) | 설정 키(차순) |
|------|-----------|-----------------|---------------|
| 카페 메인 수집 | `data/cafe_data.db` | `CAFESCRAPER_DB_PATH` | `crawler_config.json` → `db_path` |
| 이벤트 댓글·추첨 | `data/event_analysis.db` | `CAFESCRAPER_EVENT_DB_PATH` | `event_db_path` |
| 논문(위키) 수집 | `data/paper_collection.db` | `CAFESCRAPER_PAPER_DB_PATH` | `paper_db_path` |
| 자동 댓글러 | `data/auto_commenter.db` | `CAFESCRAPER_COMMENTER_DB_PATH` | `commenter_db_path` |

구현은 `app/utils/paths.py`의 `resolve_*_db_path`를 따릅니다.

공통:

- 연결 시 `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=30000` 시도 (`sqlite_db` / `event_db`).

---

## A. 카페·논문 공용 초기화 (`init_db` — `sqlite_db.py`)

`init_db(db_path)`는 **같은 파일**에 아래 세 테이블을 둡니다.  
실제로는 메인 카페 수집은 `cafe_data.db`, 논문 페이지는 별도 `paper_collection.db`를 쓰며, 후자에서는 주로 `papers`만 채웁니다.

### `posts` (카페 게시글)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| post_id | TEXT | PK |
| member_id | TEXT | 작성자 식별자 |
| nickname | TEXT | 닉네임 |
| title, content | TEXT | 제목·본문 |
| date | TEXT | 작성일 |
| board_name | TEXT | 게시판명 |
| category | TEXT | 구버전 호환용 `ALTER` 추가 |
| view_count, like_count | INTEGER | 조회·공감 |
| member_level | TEXT | 등급 문자열 |
| url | TEXT | 글 URL |
| created_at | TIMESTAMP | 기본 `CURRENT_TIMESTAMP` |

### `comments` (카페 댓글)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| comment_id | INTEGER | PK AUTOINCREMENT |
| post_id | TEXT | `posts.post_id` FK |
| writer_id | TEXT | 작성자 키 |
| nickname | TEXT | 닉네임 |
| content | TEXT | 내용 |
| is_target | INTEGER | 수집 대상 플래그 |

### `papers` (VitaminDWiki 등 페이지)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| url | TEXT | PK |
| title, summary, content | TEXT | 제목·요약·본문 |
| category | TEXT | 태그 등 |
| collected_date | TEXT | 수집일 |
| created_at | TIMESTAMP | 기본 `CURRENT_TIMESTAMP` |

**논문 DB 호환:** `02_paper_collection.py`의 `ensure_papers_schema()`가 `content` 컬럼 없으면 `ALTER` + `summary` 백필.

---

## B. 이벤트·자동댓글러 (`init_event_db` — `event_db.py`)

동일 함수가 **이벤트 전용 DB**와 **자동 댓글러 DB** 양쪽에 사용됩니다. 자동 댓글러는 실행상 `commenter_targets` 위주로 쓰입니다.

### `event_comments`

댓글 단위 저장. **UNIQUE** `(post_id, comment_writer_id, comment_date, content_hash)`.

주요 컬럼: `post_id`, `post_url`, `post_title`, `post_date`, `board_name`, `comment_id`, `comment_writer_id`, `comment_level`, `comment_grade_code`, `comment_nickname`, `comment_date`, `comment_content`, `comment_length`, `emoji_count`, `inline_image_count`, `text_char_count`, `content_hash`, `created_at`.

구버전용 `ALTER`: `comment_id`, `comment_level`, `comment_grade_code`, `comment_length`, `emoji_count`, `inline_image_count`, `text_char_count` 등.

### `event_posts`

게시글 메타·집계. `post_id` **UNIQUE**.

컬럼: `post_url`, `post_title`, `post_title_char_count`, `post_date`, `board_name`, `comments_seen`, `comments_saved`, `comments_excluded`, `author_nickname`, `post_char_count`, `post_image_count`, `created_at`, `updated_at`.

구버전 `ALTER`: `author_nickname`, `post_char_count`, `post_image_count`, `post_title_char_count`.

### `event_post_analysis`

조건2(게시글 분석) 결과. `post_id` **UNIQUE**.  
컬럼 구조는 `event_posts`와 유사한 분석용 필드 (`author_nickname`, `post_char_count`, `post_image_count`, `post_title_char_count`, 타임스탬프).

### `event_mentor_visits`

멘토 방문 스냅샷. **UNIQUE** `(nickname, member_grade)`.  
컬럼: `visit_count`, `last_visit_date`, `collect_seq`, `updated_at`.

### `commenter_targets`

자동 댓글러 타겟 스냅샷. `url` **NOT NULL UNIQUE**.

컬럼: `post_id`, `url`, `nickname`, `title`, `date`, `board_name`, `saved_at`,  
구버전 `ALTER`: `comment_status`, `comment_detail`, `comment_tried_at`.

---

## C. 마이그레이션·레거시

과거 일회성 스크립트는 `_archive_scripts/migrate_db.py` 등에 있을 수 있으며, **현행 앱은 위 모듈의 `CREATE TABLE IF NOT EXISTS` + `ALTER` 블록**으로 구 DB를 끌어올립니다.
