# 🔱 Monster 공통 라이브러리 연동 가이드

- **문서 번호**: 3M-DOC-003
- **버전**: v1.0
- **갱신 일시**: 2026-05-18
- **관리 주체**: Monster 총괄 AI (Hub AI)

---

본 문서는 미래 세션의 몬스터 AI가 개별 앱(예: NPlace-DB, CafeCrawler 등)의 소스 코드 내부에 공통 '라이브러리' 패키지를 안전하게 이식하고 결합하기 위한 연동 표준 가이드입니다. 

---

## 1. 개요 및 이식 프로세스

개별 앱 개발 시, 라이선스 검증, 자동 업데이트, 표준 에러 로그 등의 공통 시스템 기능은 개별 구현하지 않고, 3Monster 루트의 `라이브러리/` 폴더를 그대로 대상 프로젝트 루트로 복사하여 연동합니다.

### [기본 이식 절차]
1. 허브 루트(`d:\3Monster\라이브러리`) 폴더를 대상 개별 앱 프로젝트의 루트 디렉토리에 복사합니다.
2. 개별 앱의 GUI 진입부(`auth_gui.py` 등) 및 메인 스레드(`gui_main.py` 등)에서 본 가이드를 준수하여 API를 호출합니다.

---

## 2. 라이브러리 모듈별 API 규격

### A. 라이선스 검증 (`라이브러리.auth`)
- **역할**: Supabase Cloud DB의 `licenses` 테이블을 실시간 검증하고, 기기 고유 HWID를 강제 바인딩(1PC 1Key)합니다.
- **예제 연동 코드**:

```python
from 라이브러리.auth import MonsterAuth

# 1. 인스턴스 생성 (대상 제품 식별자와 사용자가 입력한 라이선스 키 전달)
auth = MonsterAuth(product_id="NPlace-DB", license_key="PRO-1234-5678")

# 2. 검증 실행 (status: True/False, message: 안내 메시지)
status, message = auth.verify_license()

if not status:
    # 인증 실패 시 UI에서 경고 창을 띄우고 앱 강제 종료 처리
    show_error_popup(message)
    sys.exit()
else:
    # 인증 성공 시 메인 화면 진입
    enter_main_dashboard()
```

---

### B. 자동 업데이트 (`라이브러리.updater`)
- **역할**: 앱 시작 시 Supabase `app_versions`를 조회하고, 신규 버전이 존재할 경우 바이너리를 받아 로컬 패치를 수행합니다.
- **예제 연동 코드**:

```python
from 라이브러리.updater import MonsterUpdater

CURRENT_VERSION = "1.0.0"

# 1. 최신 버전 정보 확인
update_info = MonsterUpdater.check_for_updates(product_id="NPlace-DB", current_version=CURRENT_VERSION)

if update_info:
    # update_info는 'version', 'download_url' 정보를 가짐
    if ask_user_to_update(latest_version=update_info['version']):
        # 로컬 다운로드 및 패치 스크립트 실행
        success = MonsterUpdater.download_to(
            download_url=update_info['download_url'], 
            save_path="update_package.zip"
        )
        if success:
            trigger_self_patching_and_restart()
```

---

### C. 에러 로깅 & 원클릭 복사 (`라이브러리.logger`)
- **역할**: 모든 오류를 `app_debug.log` 파일에 일관되게 기록하고, 사용자에게 표준화된 에러 팝업을 노출할 수 있도록 지원합니다.
- **예제 연동 코드**:

```python
from 라이브러리.logger import MonsterLogger

# 1. 로거 인스턴스 생성
monster_logger = MonsterLogger(product_id="NPlace-DB")

try:
    # 개별 앱의 수집/발송 등 핵심 기능 작동부
    run_place_crawler()
except Exception as e:
    # 2. app_debug.log에 trace 기록 및 대시보드 스크롤 박스에 에러 노출
    monster_logger.error("크롤러 실행 중 예기치 못한 에러 발생", exc_info=True)
    
    # 3. 클립보드 복사 텍스트 포맷 빌드 (원클릭 복사용)
    clipboard_text = monster_logger.get_clipboard_error_text(e)
    set_clipboard(clipboard_text)
    
    # 4. 고객지원 이동 안내 팝업 노출
    show_support_modal_with_link(
        message="오류가 발생하여 상세 로그가 클립보드에 복사되었습니다.\n고객센터 이동 후 바로 붙여넣기 하세요."
    )
```

---

### D. 데이터 내보내기 & 탐색기 포커싱 (`라이브러리.exporter`)
- **역할**: 모든 엑셀/CSV 데이터 내보내기를 시스템 '다운로드' 폴더로 일원화하고, 중복을 방지하기 위한 간소화된 날짜 포맷(`MMDD_HHMM`) 파일명 빌딩 및 내보내기 완료 시 해당 파일을 탐색기에서 자동 포커싱하는 기능을 제공합니다.
- **예제 연동 코드**:

```python
from 라이브러리.exporter import MonsterExporter

# 1. 파일 내보내기 최종 경로 생성 (식별자 prefix: 제품ID 또는 사용자정의 이벤트명 설정 가능)
# 예: nplace.naver.com_0603_1426.xlsx 또는 강남네일샵_0603_1426.xlsx
prefix = "nplace.naver.com"  # 혹은 "강남네일샵"
export_path = MonsterExporter.get_export_filepath(prefix=prefix, extension="xlsx")

# 2. 개별 앱의 데이터 내보내기 로직 실행 (예: pandas / openpyxl 활용)
df.to_excel(export_path, index=False)

# 3. 내보내기 완료 후 윈도우 탐색기(Explorer)를 실행하여 해당 경로에 파일을 포커싱/하이라이트 처리
success = MonsterExporter.open_in_explorer(export_path)

if success:
    show_success_popup(f"다운로드 폴더에 성공적으로 저장되었습니다:\n{os.path.basename(export_path)}")
```

---

## 3. 후속 AI 연동 시 준수할 5대 수칙

1. **난독화 필수**: 개별 앱 빌드 배포(`build.bat` 등을 통한 PyInstaller 작업) 전, 반드시 `라이브러리/` 패키지를 난독화 컴파일하여 빌드에 포함시켜야 합니다. (Supabase Anon Key 유출 방지 및 라이선스 Bypass 무력화).
2. **0.5초 네트워크 타임아웃**: Supabase 및 외부 네트워크 요청(Check Updates, Auth 등) 시 타임아웃은 **최대 0.5초**로 한정하여, 서버 먹통 상황에서 개별 앱의 GUI가 멈춘 것처럼(Deadlock) 보이는 현상을 원천 방지하십시오.
3. **체험 키(TEST-) 특수 처리**: `TEST-`로 시작하는 시리얼 키 감증 성공 시, 라이브러리는 `verify_license` 결과값으로 체험용 건수 한도(`collection_limit` 등)를 반환해야 하며, 개별 앱 UI는 이에 맞춰 작동 한도를 설정해야 합니다.
4. **로컬 SQLite 독립화**: 개별 앱의 로컬 SQLite는 라이브러리 영역이 아니라 개별 앱 고유의 SQLite DB 파일을 사용하여 읽고 써야 합니다. 공통 라이브러리 소스에는 어떠한 로컬 DB 관련 하드코딩도 삽입하지 마십시오.
5. **로그 파일 상한**: `app_debug.log` 파일은 단일 파일 크기가 5MB를 초과하지 않도록 회전 로깅(Rotating File Handler) 규칙을 강제 적용하십시오.

---
*Since 2026-05-18 by Monster*
