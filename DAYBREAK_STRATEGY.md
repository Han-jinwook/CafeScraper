# 🌅 Project DAYBREAK: 완전 자동화 크롤링 전략

## 📋 핵심 목표

**네이버 카페 5만 개+ 게시글 및 관계 중심 댓글 자동 수집**

---

## 🎯 전략 개요

### 1. **완전 자동화** (No Manual Intervention)
- ❌ 수동 페이지 넘기기 불가 (5만 개 처리 불가능)
- ✅ `undetected-chromedriver`로 봇 탐지 우회
- ✅ 로그인 세션 유지 (Chrome Profile 활용)

### 2. **관계 중심 수집** (Relationship-Focused)
- 모든 댓글을 저장하지 않음
- **수집 대상 댓글**:
  1. 본문 작성자가 자신의 글에 단 댓글 (질문/답변 맥락)
  2. 운영자(멀린, 마법사멀린 등)가 단 댓글 (솔루션)
- **제외**: 일반 회원의 단순 감상/잡담 댓글

### 3. **식별자 우선** (ID over Nickname)
- 닉네임은 자주 변경됨
- **`member_id`** (네이버 고유 ID) 필수 추출
- `onclick="ui(event, 'MEMBER_ID', ...)"` 파싱

### 4. **이미지 대체** (Image Placeholder)
- 이미지 다운로드 ❌ (속도 향상)
- 본문 내 `<img>` 태그 → `[이미지]` 텍스트 대체

---

## 🛠️ 기술 스택

| 항목 | 기술 | 목적 |
|------|------|------|
| **브라우저 자동화** | `undetected-chromedriver` | 봇 탐지 우회 |
| **데이터베이스** | SQLite (`cafe_data.db`) | 로컬 빠른 처리 |
| **UI** | Streamlit | 실시간 진행 상황 표시 |
| **식별자 추출** | Selenium + Regex | `member_id` 파싱 |
| **Anti-Detection** | Random delay, User-Agent | 사람 흉내 |

---

## 📊 데이터베이스 스키마

### A. `posts` (게시글)
```sql
CREATE TABLE posts (
    post_id TEXT PRIMARY KEY,
    member_id TEXT,           -- 작성자 고유 ID
    nickname TEXT,
    title TEXT,
    content TEXT,             -- 순수 텍스트 (이미지 → [이미지])
    date TEXT,                -- YYYY-MM-DD
    url TEXT
);
```

### B. `comments` (댓글)
```sql
CREATE TABLE comments (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    writer_id TEXT,           -- 댓글 작성자 member_id
    nickname TEXT,
    content TEXT,
    is_target INTEGER         -- 1: 수집 대상 (본문 작성자 or 운영자)
);
```

---

## 🚀 실행 방법

### 1. 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 2. 앱 실행
```bash
streamlit run app.py
```

### 3. 사용 순서
1. **사이드바 설정**:
   - 크롬 프로필 경로 입력
   - 운영자 닉네임 입력 (쉼표로 구분)
   - 수집 기간 설정 (💡 1년 단위 권장)
   - 게시판 URL 입력 (전체글보기 권장)

2. **1단계**: "브라우저 열기" → 로그인 확인

3. **2단계**: "크롤링 시작"
   - 실시간 로그 확인
   - 진행률 표시

4. **DB 확인**: "저장된 데이터 확인" 체크박스

---

## 💡 팁 & 주의사항

### ✅ 권장사항
- **11년치 데이터**: 1년 단위로 끊어서 수집
- **전체글보기** 메뉴 사용 (모든 카테고리 수집)
- **디버그 모드**: 첫 테스트 시에만 활성화 (속도 저하)

### ⚠️ 주의사항
- Chrome 브라우저를 **완전히 종료**한 후 실행
- 프로필 경로가 정확한지 확인
- 수집 중 브라우저 조작 금지

### 🔧 문제 해결
- **Chrome 버전 오류**: `crawler.py`의 `version_main=144` 수정
- **멈춤 현상**: 디버그 모드 활성화 후 로그 확인
- **로그인 실패**: 1단계에서 수동 로그인 후 진행

---

## 📝 재니미의 핵심 조언

> "5만 개를 수동으로 처리할 수는 없어. 완전 자동화가 필수야."

> "`undetected-chromedriver`로 네이버 봇 탐지를 우회하고, `member_id`로 닉네임 변경에 대응해."

> "댓글은 전부 저장하지 마. 본문 작성자와 운영자 댓글만 수집하면 돼."

---

## 📈 진행 상황 모니터링

### 실시간 로그 예시 (프로덕션 모드)
```
[13:08:35] ✅ 10페이지 완료: 0개 수집
[13:08:32] ✅ 9페이지 완료: 0개 수집
[13:08:26] 🚀 10페이지 분석 시작 (누적: 0개)
[13:08:23] ✅ 9페이지 완료: 0개 수집
[13:08:17] 🚀 9페이지 분석 시작 (누적: 0개)
```

### 디버그 모드 (문제 발생 시)
```
[디버그 1] 행 텍스트: 이것은 제목입니다
[디버그 1] 날짜: '2025.01.20' -> 2025-01-20
[디버그 1] ✅ 수집 성공: 이것은 제목입니다
```

---

## 🎯 성공 기준

- ✅ 5만 개 게시글 자동 수집
- ✅ 작성자 `member_id` 100% 추출
- ✅ 관계 중심 댓글만 필터링
- ✅ 로컬 SQLite DB 저장
- ✅ 네이버 봇 탐지 우회
- ✅ 재개 기능 (중복 스킵)

---

**Last Updated**: 2026-01-27  
**Status**: 🚧 테스트 진행 중  
**Author**: Anti-Gravity Team + 재니미
