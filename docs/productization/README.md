# Productization Workspace (문서)

- 작성 일시: 2026-02-11 16:52:18
- 최종 업데이트: 2026-03-20

**실행 스크립트**(`create_workspace.py`, `profiles.json`, `runtime/` …)는 리포지토리 **`productization/`** 폴더(이 문서의 상위 sibling)에 있습니다.

현재 통합 레포에서 제품별 배포용 워크스페이스를 자동 생성하는 도구입니다.

## 목적
- 개발은 통합 코어(단일 소스)로 유지
- 배포는 제품별(단품/통합본) 워크스페이스로 분리
- 현재 통합본 실행에는 영향 없이, 제품화 준비만 진행

**브랜드:** 우산 `3Monster` — 카페 몬스터 / 마케팅 몬스터 / 앱 몬스터(예정). 상세는 이 폴더의 `BRAND_GUIDE_3MONSTER.md`.

## 문서 목록 (`docs/productization/`)
- `BRAND_GUIDE_3MONSTER.md` — 우산 브랜드
- `BRAND_GUIDE_CafeMonster.md` — 카페 몬스터 CI/BI
- `NAMING_MATRIX_CafeMonster.md` — 제품/파일명 네이밍
- `STITCH_PROMPT_CAFE_CRAWLER_KO.md` — Stitch UI 프롬프트

## 실행 자산 목록 (리포 루트 `productization/`)
- `profiles.json`
- `create_workspace.py`
- `requirements_product.txt`
- `runtime/`

## 사용법

```powershell
python productization/create_workspace.py --profile integrated
python productization/create_workspace.py --profile crawler_basic
python productization/create_workspace.py --profile event_picker
python productization/create_workspace.py --profile commenter
python productization/create_workspace.py --profile paper_collector
```

생성 결과:
- `build_products/<profile>/`
  - `.streamlit/pages.toml` (제품 전용 메뉴)
  - `run_product.bat` (실행 스크립트)
  - `run_product_desktop.bat` (주소창 없는 데스크톱 실행)
  - `PRODUCT_META.json` (엔트리/타이틀 메타)
  - `branding/CafeMonster_logo.png` (브랜드 로고)
  - 필요한 앱 코드 사본
  - `runtime/*` (라이선스 검증/런처)

## 라이선스 발급/검증(1카페 바인딩)

```powershell
# 1) 키 생성 (최초 1회)
python productization/runtime/generate_keys.py

# 2) 라이선스 발급 (예: 6개월, 특정 카페)
python productization/runtime/issue_license.py --product CafeMonster_Crawler_Pro --cafe https://cafe.naver.com/sundreamd --term 6m --out license.lic

# 3) 검증 테스트
python productization/runtime/verify_license.py --product CafeMonster_Crawler_Pro --license-file license.lic --public-key productization/keys/ed25519_public.pem --config crawler_config.json
```

라이선스 정책:
- 기간: `1m`, `6m`, `1y`, `permanent`
- 바인딩: 카페 1개 (`cafe_url` 또는 `board_url`에서 식별)
- 서명: Ed25519

## 주의
- 이 단계는 "워크스페이스 생성"만 담당합니다.
- 실제 exe 빌드(PyInstaller)는 다음 단계에서 별도 스크립트로 추가 예정입니다.
