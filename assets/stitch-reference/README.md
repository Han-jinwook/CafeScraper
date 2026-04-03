# Stitch UI 시안 참고물 (읽기 전용)

Streamlit 앱(`app.py`, `pages/`)을 **디자인만** 맞출 때 쓰는 **참고 파일**을 여기 둡니다.

## 현재 들어 있는 산출물 (확인됨)

| 폴더 / 파일 | 역할 (목업) | 우리 앱에 반영할 때 |
|-------------|-------------|---------------------|
| `monster_logic_pro/DESIGN.md` | **디자인 시스템** (컬러·타이포·레이어·컴포넌트 규칙) | 토큰·원칙의 **단일 기준**. HTML과 숫자가 어긋나면 **이 파일 우선**. |
| `v2_cafemonster_crawler_setup/` | 설정·실행 제어 화면 (`code.html`, `screen.png`) | **`app.py`** 메인 영역: **상단** 브랜딩·**전폭 설정+DB 카드** → **하단** 실행·진행·리스트 (위젯·키·로직 동일). |
| `v2_cafemonster_live_dashboard/` | 진행 중 대시보드 | **`app.py`** `_render_cafe_main_workspace()` 안 진행·로그 영역 (동작 동일). |
| `v2_cafemonster_results_logs/` | 완료 후 요약·로그 | 같은 함수 내 결과·데이터 관리 탭 (동작 동일). |

**중요:** 위 `code.html` 은 Tailwind 정적 목업입니다. **기능·데이터 바인딩이 없습니다.**  
구현 시 **절대** 그 HTML을 그대로 끼워 넣지 않고, **지금 돌아가는 Streamlit 위젯 + 세션 상태**만 유지한 채 CSS·폰트·색만 맞춥니다.

`pages/02_논문_수집.py` 는 **마케팅 몬스터** 라인이라 위 3폴더와 1:1 대응은 아닙니다. 카페 몬스터 톤이 필요하면 같은 토큰만 선택 적용하면 됩니다.

## 반드시 지킬 것

- **기존 크롤링·DB·세션·버튼·키(`key=`) 동작은 변경하지 않습니다.**
- Stitch 산출물은 **시각 참고**일 뿐, **팩트(실제 필드·플로·에러 처리)** 는 코드베이스 기준입니다.

## 관련 문서

- Stitch용 프롬프트: [`docs/productization/STITCH_PROMPT_CAFE_CRAWLER_KO.md`](../../docs/productization/STITCH_PROMPT_CAFE_CRAWLER_KO.md)
- 브랜드: [`docs/productization/BRAND_GUIDE_CafeMonster.md`](../../docs/productization/BRAND_GUIDE_CafeMonster.md)
