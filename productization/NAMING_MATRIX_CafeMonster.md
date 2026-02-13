# [카페 몬스터] 제품 네이밍 매트릭스

브랜드 규칙: `CafeMonster_[Feature]_[Version]_v[Release].exe`

## 서비스 매핑(출시 SKU 기준)

| 구분 | 한글 정식 명칭 | 영문/시스템 식별자 | 권장 EXE 파일명 (v1.0) |
|---|---|---|---|
| 카페 추출 | [카페 몬스터] 카페 추출기 Pro | `CafeMonster_Crawler_Pro` | `CafeMonster_Crawler_Pro_v1.0.exe` |
| 댓글 관리 | [카페 몬스터] 스텔스 댓글러 | `CafeMonster_StealthComment` | `CafeMonster_StealthComment_v1.0.exe` |
| 논문 수집 | [카페 몬스터] 논문 수집기 | `CafeMonster_PaperCrawler` | `CafeMonster_PaperCrawler_v1.0.exe` |
| 플레이스 수집 | [카페 몬스터] 플레이스 DB Pro | `CafeMonster_PlaceDB_Pro` | `CafeMonster_PlaceDB_Pro_v1.0.exe` |

## 현재 프로필 전체 매핑(빌드 자동화 기준)

| profile key | 표시명 | system_id | 권장 EXE 파일명 |
|---|---|---|---|
| `integrated` | `[카페 몬스터] 통합본 Master` | `CafeMonster_MasterSuite` | `CafeMonster_MasterSuite_v1.0.exe` |
| `crawler_basic` | `[카페 몬스터] 카페 추출기 Pro` | `CafeMonster_Crawler_Pro` | `CafeMonster_Crawler_Pro_v1.0.exe` |
| `commenter` | `[카페 몬스터] 스텔스 댓글러` | `CafeMonster_StealthComment` | `CafeMonster_StealthComment_v1.0.exe` |
| `paper_collector` | `[카페 몬스터] 논문 수집기` | `CafeMonster_PaperCrawler` | `CafeMonster_PaperCrawler_v1.0.exe` |
| `event_picker` | `[카페 몬스터] 이벤트 추첨기` | `CafeMonster_EventPicker` | `CafeMonster_EventPicker_v1.0.exe` |
| `place_db_pro` | `[카페 몬스터] 플레이스 DB Pro` | `CafeMonster_PlaceDB_Pro` | `CafeMonster_PlaceDB_Pro_v1.0.exe` |

## 내부 UI 타이틀 규칙
- 형식: `[카페 몬스터] {서비스명} {버전}`
- 예시: `[카페 몬스터] 카페 추출기 Pro V1.0`
