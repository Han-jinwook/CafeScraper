# [카페 몬스터] 브랜드 통합 가이드 적용 메모

- 작성 일시: 2026-02-12 11:00:07
- 최종 업데이트: 2026-03-20

**우산 브랜드:** `3Monster` — 하위에 카페 몬스터 / 마케팅 몬스터 / 앱 몬스터(예정) 분화.  
상위 구조는 **`BRAND_GUIDE_3MONSTER.md`** 참고.

본 문서는 현재 코드/패키징 스크립트에 반영된 **카페 몬스터** 브랜드 규칙을 정리합니다.

## 1) 명칭/식별자 적용
- `CafeMonster_Crawler_Pro`
- `CafeMonster_StealthComment`
- `CafeMonster_PaperCrawler`
- `CafeMonster_PlaceDB_Pro` (프로필 예약)

프로필 파일:
- `productization/profiles.json`

## 2) EXE 네이밍 규칙 적용
- 규칙: `CafeMonster_[Feature]_[Version]_v[Release].exe`
- 워크스페이스 생성 시 `PRODUCT_META.json`에 권장 파일명 자동 기록

## 3) 내부 타이틀 규칙
- 형식: `[카페 몬스터] {서비스명} {버전}`
- 각 제품 프로필의 `page_title`/`display_name`에 반영

## 4) 로컬 폴더 규칙
- 규칙: `C:/CafeMonster/[Feature]/...`
- 워크스페이스 메타(`PRODUCT_META.json`)에 경로 정책 반영:
  - `root`
  - `data` (`.../data/database.sqlite`)

## 5) 시리얼 인증 문구
- 런처 검증 실패 시 다음 문구 출력:
  - `대한민국 No.1 카페 마케팅의 괴물, 카페 몬스터의 시리얼 번호를 입력하세요.`

## 6) 코어 무변경 원칙
- 본 브랜드 작업은 패키징 계층(`productization/*`) 중심으로 반영
- 크롤링 코어(`app/products/scraper/crawler.py`)는 변경하지 않음
