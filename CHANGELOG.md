<!-- CafeScraper 1.3.23 -->

# 변경 이력

**규칙:** 릴리스할 때마다 루트 `version.txt`의 **semver**(한 줄)를 바꾸고, 여기 **맨 위에** 요약 블록을 추가합니다.
- **패치(+끝자리):** 작은 수정, 버그픽스, 문구/UI만, 의미 있는 동작 변경이 거의 없을 때.
- **마이너(+가운뎃자리):** 새 기능·흐름 추가, 동작 방식이 눈에 띄게 바뀌지만 기존 쓰는 사람 입장에서 “큰 깨짐”은 아닐 때.
- **메이저(+맨 앞자리):** 호환 깨지는 변경(설정 형식 폐기, API/파일 규격 불일치 등) 때.

## 1.3.23 — 2026-05-18

- **자동댓글러:** 📖 가이드에 **안전 사용 조건**(300건/일·당일 재실행 금지·제재 가능성) 정리. 댓글마다 **`{인사}` 무작위**(`COMMENTER_GREETING_VARIANTS`), 기본 템플릿·맨 앞 「안녕하세요」 치환.

## 1.3.22 — 2026-05-18

- **자동댓글러:** 📖 사용 가이드에 **댓글 간격·N건 단위 휴식** 설명 및 **하루 약 300건 이하 권장** 문구 추가(고정 정책, 커스텀 UI 없음).

## 1.3.21 — 2026-05-15

- **자동댓글러 템플릿:** `comment_templates.json`을 **`get_comment_templates_path()`**(exe·루트)로 고정, **`build.bat`**·**`pick_prior_dist_dir.ps1`** 마이그레이션에 포함. 기본 하드코딩 문장 **1개** + `(직접 입력)` 만 표시.
- **배포 ZIP:** **`pack_dist.ps1`** 에서 `comment_templates.json` 제외(로컬 설정 성격).
- **빌드:** exe 옆으로 **`version.txt` 복사 제거** — 폴더명 semver는 루트 `version.txt`, 앱 표시는 번들 `_internal` 유지.

## 1.3.20 — 2026-05-15

- **자동댓글러:** 목록/표 작성자 셀에 붙는 **`멤버등급 : 일반멤버`** 등 접미 제거 — `sanitize_commenter_nickname`, `_normalize_nickname` 보강, 템플릿 치환·댓글 작성·타겟 표(표시)에 적용.
- **댓글 미리보기:** 이메일 스타일 **`To. … :`** 제거, 치환된 **본문만** 표시.
- **기본 예시 템플릿:** `{닉네임}` → `{작성자}` (표·안내와 통일).

## 1.3.19 — 2026-05-15

- **자동댓글러:** 댓글 템플릿 **`{작성자}`** 토큰 추가(DB 컬럼 `nickname`·UI 「작성자」와 동일 값). **`{닉네임}`·`{제목}`** 유지. 치환 **`apply_comment_template_placeholders`** 로 통일(`bot.py`).
- **UI:** 템플릿 `help(?)` 제거, **`{작성자} 치환 가능`** 인라인 표기. 타겟 표 인덱스는 사용자 요청에 따라 숨기지 않음.

## 1.3.18 — 2026-05-15

- **자동댓글러 2단계:** 닉네임이 모두 `unknown`일 때 **`drop_duplicates(nickname)`으로 수백 건이 1건으로 줄어들던** 문제 수정 — `unknown` 행은 **URL 기준**으로 구분해 중복 제거.
- **목록 작성자 추출:** 표형 게시판(`td.td_name` 등) 셀렉터 보강, 유효 닉을 찾으면 즉시 채택(기존: `member_id`만으로 break); **`tr`/`td` 열 휴리스틱** 폴백. `_normalize_nickname`에서 목록 등급 **`[1]`** 접미 제거.

## 1.3.17 — 2026-05-15

- **자동댓글러 목록 수집:** `_switch_to_cafe_iframe()`이 `cafe_main` 대기 실패 시에도 **성공으로 넘어가 부모 문서에서 빈 목록을 보던** 케이스를 줄이기 위해 **mainFrame·name·src 기반 폴백**을 추가하고, 전부 실패 시 **안내 메시지·`False` 반환**.
- **목록 파싱:** `time[datetime]` 날짜, 제목 링크 셀렉터 보강; 목록 단계에서 **닉 레이어 클릭(`prefer_layer`) 비활성화**로 지연·간섭 완화.
- **타겟 DB 저장:** `replace_commenter_targets` 예외를 삼키지 않고 **`st.warning`** 으로 표시.

## 1.3.16 — 2026-05-14

- **자동댓글러 2단계:** 목록 수집 후 후보 글마다 `scrape_article_detail`을 호출하던 로직 제거 — 목록에 닉·게시판이 없으면 잠시 불완전하더라도 **수집이 사실상 멈춘 것처럼 보이던 병목** 해소. 목록 배치마다 진행 문구에 누적 건수 표시.

## 1.3.15 — 2026-05-14

- **`scrape_board_list` 견고화:** 네이버 카페 목록 DOM 변경 시 행만 잡히고 글이 0건 되던 경우를 줄이기 위해 **게시글 링크 기반 폴백 수집**(`_fallback_collect_board_list_rows`), 목록 행 셀렉터 확장, 행이 비어 보일 때도 폴백 시도.

## 1.3.14 — 2026-05-14

- **데이터 초기화 UI 통일:** 이벤트 댓글·카페 수집 메인(`app`)·자동댓글러 — 노란/경고 블록+이중 안내 없이 **`[ ] 안내 한 줄`** + **`데이터 초기화`** 버튼만 같은 형태로 정리.

## 1.3.13 — 2026-05-14

- **자동 댓글러 DB 패널:** 실제 적용 경로만 읽기 전용 표시·**DB 경로 저장** 제거·노란 안내 상자 제거. 초기화는 체크박스(안내 두 줄)·**댓글 대상 DB 초기화** 단추만 사용.

## 1.3.12 — 2026-05-14

- **`build.bat` semver 올릴 때 사용자 데이터 이관:** `dist\cafescraper_V{신버전}` 이 아직 없거나 비어 있어도, `dist` 안 **가장 semver가 큰 이전 `cafescraper_V*.*.*` 폴더**에서 `data\`, `crawler_config.json`, `sessions\`, `snapshots\`를 찾아 새 빌드 폴더로 백업·복구. (`scripts\pick_prior_dist_dir.ps1`)

## 1.3.11 — 2026-05-14

- **자동 댓글러:** `2단계: 타겟 목록 수집` 버튼이 먹통처럼 보이던 경우 수정 — `st.rerun()` 직후 `_commenter_run_collect` 플래그만 유실되면 `commenter_collecting=True` 만 남아 버튼이 계속 비활성처럼 동작할 수 있어, 클릭 시 **바로 `_collect_commenter_targets_into_session()` 호출**로 변경. 차단 상태에서는 Primary가 아니라 Secondary 버튼으로 표시하고 도움말 추가.

## 1.3.10 — 2026-05-14

- **자동 댓글러:** 카페명·카페 URL을 `crawler_config.json`에 저장한 뒤에도 페이지를 벗어나면 빈 칸처럼 보이던 현상 수정 — 새 세션에서 `commenter_cafe_*` 설정을 세션 상태에 채움, 저장되어 있으면 연결 단추는 `리셋` 상태로 표시.
- **자동 댓글러 UI:** DB 경로·댓글 대상 건수·초기화 블록을 **가운데 패널(타겟 수집 설정)** 하단으로 옮기고 **`💾 DB 경로 · 댓글 대상 (접기/펼치기)`** expander로 정리.

## 1.3.9 — 2026-05-14

- **`build.bat` 재빌드 시 사용자 데이터 이관 보강:** `data\` 외에 exe 옆 **`crawler_config.json`**, **`sessions\`**, **`snapshots\`** 도 백업·복구(기존엔 설정·세션만 초기화되는 문제 가능).
- semver 안내 문구 및 복구 실패 시 `dist\_user_data_backup` 유지 경고 보강.

## 1.3.8 — 2026-05-14

- **배포 폴더명에 버전 표기:** PyInstaller 산출물이 `dist\CafeScraper` 고정이 아니라 **`dist\cafescraper_V{semver}`** (`version.txt` 한 줄과 동일)로 생성되도록 `cafescraper.spec`·`build.bat`·`scripts\pack_dist.ps1` 정렬. 탐색기에서 빌드 구분 가능.
- 예전 레이아웃 `dist\CafeScraper\` 폴더가 남아 있으면 `build.bat` 끝에서 안내하고, 필요 시 직접 삭제하면 됩니다.

## 1.3.7 — 2026-05-13

- **카페명·URL 행 통일:** 카페 수집(`app.py`), 이벤트 댓글(`pages/03_event_comment_lottery.py`), 자동 댓글러(`pages/04_auto_commenter.py`) 모두 URL 줄을 `[입력창 | 저장 | 초기화]` 3열로 맞춤. 리셋 후에만 저장이 보이던 이중 단계 제거.
- 메인 카페 수집: 카페명 입력 기본값에서 `'카페 몬스터'` 자동 채움 제거(저장된 설정만 표시, 없으면 빈 칸).

## 1.3.6 — 2026-05-13

- 번들에 `pyperclip`이 빠져 자동 댓글러에서 `ModuleNotFoundError`가 나던 문제: 빌드 환경에 패키지 설치 및 `cafescraper.spec`에서 `collect_all('pyperclip')`.
- 데스크톱 빌드에서 `webview` 미포함 방지를 위해 `run_app.py` 모듈 레벨 정적 import 유지.
- **버전 표기:** `version.txt` 단일 소스, `app/utils/app_version.py`, Streamlit 탭 제목·pywebview 창 제목 반영, 번들 `_internal` 및 배포 폴더에 `version.txt` 포함·복사, 본 변경 이력 파일 추가.

## 1.3.5 및 이전

- 세부 내용은 Git 기록 및 `docs/help.md` 등 문서를 참고합니다.
