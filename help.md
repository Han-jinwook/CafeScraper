# CafeScraper UI 리디자인 — 현재 상황 정리 및 새 세션 인계서

## 📌 프로젝트 기본 정보

| 항목 | 내용 |
|---|---|
| **경로** | d:\CafeScraper |
| **현재 버전** | V1.3.42 |
| **아키텍처** | Streamlit 멀티페이지 앱 (PyInstaller 빌드) |
| **진입점** | pp.py |
| **네비게이션** | pp\utils\streamlit_top_nav.py |
| **서브페이지** | pages\03_event_lottery.py, pages\04_auto_commenter.py |
| **빌드** | uild.bat → dist\cafescraper_V1.3.42\CafeScraper.exe |

---

## ❌ 현재 문제점 (이번 세션에서 해결 실패)

### 1. 카드 박스 밖으로 텍스트/요소가 삐져나옴
- 설정 카드 3개(카페연결/타겟수집설정/댓글실행) 내부 h3 제목이 카드 경계 밖으로 튀어나옴
- overflow-wrap, word-break 추가했으나 미해결
- 근본 원인: streamlit_top_nav.py inject_settings_card_style() CSS와 app.py 전역 CSS 충돌

### 2. 상하 여백이 오히려 커짐
- block-container padding-top 줄였으나 실제로는 공간이 더 벌어짐
- Streamlit 내부 gap, row-gap 기본값이 override를 씹는 것으로 추정

### 3. 레이아웃 전체적으로 통일감 없음
- 네비바, 제목, 카드가 서로 다른 스타일 언어
- 입체감 의도 그림자가 어색하게 분리된 느낌

---

## 🎯 사용자 요구 디자인

> "라이트 모드 + 딥 네이비·블루 포인트 — 깔끔하고 전문적인 비즈니스 느낌"

- 배경: 아주 연한 회색 (#f1f4f9)
- 포인트: 딥 네이비(#1e3a8a) + 블루(#2563eb)
- 입력창: 배경과 명확히 구분되는 테두리 (이전엔 입력창이 배경에 묻힘)
- 전체: 정갈하고 신뢰감 있는 비즈니스 느낌
- 기능은 절대 건드리지 말 것 (UI CSS만)

---

## 📁 주요 파일

- app.py : 메인 페이지, CSS 블록 38번줄 st.markdown 블록
- app\utils\streamlit_top_nav.py : 네비바 + 설정카드 스타일
  - render_main_top_nav() : 상단 탭 메뉴 렌더링
  - inject_settings_card_style() : 3개 카드 CSS 주입 (이곳이 문제)
- pages\03_event_lottery.py : 이벤트 추첨 페이지
- pages\04_auto_commenter.py : 자동 댓글러 페이지
- version.txt : "1.3.42"
- build.bat : PyInstaller 빌드 스크립트

---

## ✅ 이번 세션 성공한 것

1. 뷰부스터 제거 — 05_view_booster.py 삭제, 네비 메뉴 제거 완료
2. 네비바 컬럼 버그 수정 — 4개 컬럼 하드코딩 → len() 동적 처리
3. 기능 안정성 유지 — 수집 로직, DB, 빌드 시스템 모두 정상

---

## 🚀 새 세션 전략

### CSS 처음부터 재설계 원칙
1. app.py CSS 블록 전체를 단순하게 재작성
2. inject_settings_card_style() 카드 내부 CSS 중복 지정 제거
3. h1/h2/h3 폰트 사이즈 강제 override 하지 말 것 (Streamlit 기본 크기 사용)
4. Less is more: CSS override 최소화, Streamlit 기본 레이아웃 존중
5. 입력창·드롭다운에 명확한 테두리만 추가 (배경과 구분)
6. 카드: 흰 배경 + 아주 연한 파란 테두리만. 그림자 최소화

### Git 롤백 포인트
- 안전한 상태 (뷰부스터 제거+네비버그 수정): 596ff11
- 완전 안전 (뷰부스터 제거 직후): 25359b8

`
git reset --hard 596ff11
`

---

## ⚠️ 빌드 주의사항

- 빌드 전 CafeScraper.exe 반드시 종료
- 강제 종료: taskkill /F /IM CafeScraper.exe /T
