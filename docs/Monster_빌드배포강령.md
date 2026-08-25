# 🔱 Monster 하위 프로그램 빌드 및 배포 강령

- **문서 번호**: 3M-DOC-002
- **버전**: v1.0
- **갱신 일시**: 2026-08-05
- **관리 주체**: Monster 총괄 AI (Hub AI)

---

본 문서는 `3Monster` 프로젝트 산하 하위 프로그램들의 로컬 컴파일(PyInstaller 빌드), 패키징(압축), 그리고 깃허브(GitHub Releases) 및 Supabase DB 연동 자동 배포에 대한 절대 지침서입니다. 다음 세션의 AI는 반드시 이 가이드를 읽고 하부 제품들의 빌드 및 배포 작업을 수행하십시오.

---

## 🚫 배포 프로세스 철칙: 선(先) 폴더 빌드 ➡️ 후(後) 로컬 테스트 ➡️ 최종 압축 및 배포

> [!IMPORTANT]
> **빌드 전 보안 및 라이선스 사전 검증 필수**:
> 1. **보안 검증**: 소스 코드(특히 `config.py` 등) 및 로컬 패키징 영역에 민감한 API 키, GitHub PAT, DB 접속 정보 등의 크리덴셜 정보가 하드코딩되어 유출되지 않는지 철저히 사전 점검하십시오.
> 2. **라이선스 검증**: 기기별 HWID 우회 가능성, 인증 우회용 로컬 파일 조작 가능성, 그리고 등급별(PRO/TRIAL) 이용 한도 제한 메커니즘이 코드 내에 완벽하게 활성화되어 작동하는지 빌드 전에 반드시 한 번 더 검증하십시오.

모든 하부 제품의 배포 시, AI는 **자동 빌드 후 곧바로 압축(ZIP) 파일을 만들거나 깃허브 업로드를 진행해서는 안 됩니다.** 반드시 아래 단계를 엄수하십시오.
1. **1단계 (기본 엔진 폴더 빌드)**: PyInstaller 빌드만 돌려 로컬 `dist` 밑에 실행 폴더(`Map_DB-PRO`, `cafescraper_V...` 등)를 생성합니다.
2. **2단계 (개발자 테스트 대기)**: 빌드가 완료되면 작업을 멈추고 대표님께 **"기본 엔진 폴더 빌드가 완료되었습니다. 직접 실행하여 로컬 테스트를 진행해 주세요"**라고 안내합니다.
3. **3단계 (승인 후 배포)**: 대표님께서 직접 실행 파일(`.exe`)을 테스트하신 후 최종 배포 승인("배포해라", "업로드해라" 등)을 하셨을 때만 압축(ZIP) 패키징을 수행하고 깃허브 릴리즈 및 Supabase 갱신을 진행합니다.

### 🛠️ 단일 엔진 컴파일 및 설정 파일 분기 규정 (Single Engine & Runtime Config)
* **개별 빌드 금지**: 등급별(PRO / TRIAL 등)로 무거운 PyInstaller 컴파일을 따로 수행하여 여러 개의 실행 엔진 폴더를 만들지 않는다.
* **단일 엔진 컴파일**: 공통으로 실행 가능한 기본 엔진을 **단 1회만 빌드**하여 하나의 실행 폴더(예: `Map_DB-PRO-v1.1.93`, `cafescraper_V1.3.65`)만 생성한다.
* **설정 파일 분기**: 프로그램의 등급(PRO, TRIAL 등) 작동 제한 및 메인 화면 제목은 컴파일 시점에 결정하지 않고, 프로그램 실행 시 내부에 존재하는 텍스트 파일(`mode.txt` 등)의 내용을 읽어 동적으로 결정한다.
* **패키징 자동화**: 배포용 ZIP 압축 파일을 생성할 때, 공통 엔진 폴더를 스테이징(Staging)에 복사한 후 `mode.txt`에 해당 제품 사양에 맞는 값(`PRO` 또는 `TRIAL`)을 작성해 넣고 최종 압축을 완성한다.

---

## 1. N플레이스 타겟 DB 수집기 (Map_DB / N-Place-DB)

### 📂 정보 및 환경 설정
* **로컬 소스 경로**: `d:\N-Place-DB`
* **깃허브 저장소**: `https://github.com/Han-jinwook/n-place-db`
* **인증 및 자격 증명**: `.env` 파일 (루트에 위치, `GITHUB_PAT` 및 `SUPABASE_SERVICE_ROLE_KEY` 내장)
* **버전 제어 파일**: `config.py` 내 `CURRENT_VERSION = "1.1.X"` 변수

### 🛠️ 빌드 및 배포 프로세스 (프로그램별)
1. **버전 수정**: 
   * 배포 전 `config.py` 파일의 `CURRENT_VERSION`을 최신화합니다.
2. **로컬 빌드**:
   * **`build.bat`** 파일을 실행합니다.
   * `build_exe.py`가 작동하며 `config.py`의 `BUILD_TYPE`을 런타임에 동적으로 변경하여 `dist\Map_DB-PRO` 및 `dist\Map_DB-TRIAL`을 순차적으로 PyInstaller 컴파일합니다.
3. **배포 및 업로드 (자동화)**:
   * 터미널에서 **`python deploy_ota.py`** 명령을 실행합니다.
   * 이 스크립트는 **2종의 최종 ZIP 패키지**를 자동 압축 및 업로드하고 Supabase를 동기화합니다:
     1. `Map_DB-Pro.zip` (정식판 패키지)
     2. `Map_DB-Trial.zip` (체험판 패키지)
   * 깃허브 Releases에 태그(`v{Version}`)를 생성하여 위 2개 자산을 업로드하고 Supabase `app_versions` 테이블을 최종 업데이트합니다.

---

## 2. 카페 몬스터 통합본 (CafeScraper / CafeMonster)

### 📂 정보 및 환경 설정
* **로컬 소스 경로**: `d:\CafeScraper`
* **깃허브 저장소**: `https://github.com/Han-jinwook/CafeScraper`
* **인증 및 자격 증명**: `.env` 파일 (N-Place-DB의 토큰을 복사하여 루트에 보관)
* **버전 제어 파일**: `version.txt` (단 한 줄로 버전 기록, 예: `1.3.65`)

### 🛠️ 빌드 및 배포 프로세스 (프로그램별)
1. **버전 수정**: 
   * 배포 전 `version.txt`와 `CHANGELOG.md`를 갱신합니다.
2. **로컬 빌드**:
   * **`build.bat`** 파일을 실행합니다.
   * PyInstaller 컴파일러가 작동하여 `dist\cafescraper_V{Version}` 폴더에 단독 실행형 실행 파일(`CafeScraper.exe`)을 빌드합니다.
3. **패키징 (압축 분리)**:
   * **`package.bat`** 파일을 실행합니다.
   * `scripts\pack_dist.ps1` 스크립트가 실행되어 빌드된 결과물을 기반으로 `mode.txt` 분기 데이터를 동적으로 셋업하고, 프로젝트 루트에 **4종의 최종 배포용 ZIP 파일**을 구성합니다:
     * `CafeCrawler-Pro.zip` (기본 정품 모드)
     * `EventStats-Pro.zip` (기본 정품 모드)
     * `AutoComment-Pro.zip` (기본 정품 모드)
     * `CafeMonster-Trial.zip` (기본 체험판 모드 - **3개 하위 기능의 통합 체험판**)
4. **배포 및 업로드 (자동화)**:
   * 터미널에서 **`python deploy_ota.py`** 명령을 실행합니다.
   * 작성 완료된 4개의 ZIP 파일을 `Han-jinwook/CafeScraper` 깃허브의 버전 태그(`v{Version}`) Releases 페이지에 업로드합니다.
   * 동시에 Supabase `app_versions` 테이블에 `CafeCrawler`, `EventStats`, `AutoComment` 3개 제품군의 최신 버전 정보와 다운로드 URL 링크를 한 번에 갱신하여 OTA 업데이트 시스템을 동기화합니다.

---

## 3. 3Monster 통합 웹 허브 (대시보드 & 쇼룸)

### 📂 정보 및 환경 설정
* **로컬 소스 경로**: `d:\3Monster`
* **깃허브 저장소**: `https://github.com/Han-jinwook/3Monster`

### 🔗 체험판 다운로드 매핑 규칙
하위 제품들의 배포 방식이 단일화됨에 따라 쇼룸 및 어드민 대시보드 내의 Trial 다운로드 경로를 다음과 같이 고정하여 연동해야 합니다.

1. **카페 몬스터 3종 체험판 (카페수집기 / 활동분석기 / 자동댓글러)**:
   * **다운로드 연결 파일**: `CafeMonster-Trial.zip`
   * **쇼룸 코드 ([Showroom.tsx](file:///d:/3Monster/admin-dashboard/src/pages/Showroom.tsx))**:
     ```typescript
     selectedProduct.id === 'cafe-crawler' || selectedProduct.id === 'event-activity-stats' || selectedProduct.id === 'comment-stats'
         ? "https://github.com/Han-jinwook/CafeScraper/releases/latest/download/CafeMonster-Trial.zip"
     ```
   * **어드민 허브 ([LicenseGenerator.tsx](file:///d:/3Monster/admin-dashboard/src/pages/LicenseGenerator.tsx))**:
     ```typescript
     if (type === 'Trial' && (productId === 'CafeCrawler' || productId === 'EventStats' || productId === 'AutoComment')) {
         return `https://github.com/Han-jinwook/CafeScraper/releases/latest/download/CafeMonster-Trial.zip`;
     }
     ```

2. **N플레이스 DB 추출기 체험판**:
   * **다운로드 연결 파일**: `Map_DB-Trial.zip`
   * **쇼룸 코드**:
     ```typescript
     selectedProduct.id === 'nplace-db'
         ? "https://github.com/Han-jinwook/n-place-db/releases/latest/download/Map_DB-Trial.zip"
     ```

---

## 4. UI 및 OTA 업데이트 안정성 절대 규칙 (UI/OTA Safety Rules)

최근 확인된 버그를 기반으로 모든 하부 앱(`N-Place-DB`, `CafeScraper` 등)에서 공통적으로 지켜야 할 UI 렌더링 및 자동 업데이트 절대 수칙입니다.

### 4.1. 인증창(Auth GUI) 렌더링 동기화 처리 (Race Condition 방지)
- **규칙**: 인증 상태를 확인하는 로직은 GUI(`tkinter` 등) 창이 본격적으로 이벤트 루프(`mainloop()`)에 진입하기 **전**에 동기적으로 처리되어야 합니다.
- **사유**: 백그라운드 스레드에서 서버 응답을 대기하다가 `self.after(0, destroy)`를 호출하는 방식은, 네트워크 속도가 매우 빠를 경우 UI 창이 렌더링되기도 전에 종료 이벤트가 소비되어버리는 레이스 컨디션을 유발합니다. 이로 인해 인증된 사용자에게도 인증창이 닫히지 않고 계속 노출되는 치명적인 버그가 발생할 수 있습니다.

### 4.2. 식별 파일(mode.txt 등)의 인코딩 강제 (BOM 차단)
- **규칙 1 (생성 측면)**: PowerShell 등 윈도우 스크립트에서 텍스트 파일(`mode.txt`)을 생성할 때, `Set-Content -Encoding Utf8` 사용을 **절대 엄금**합니다. 대신 `-Encoding ascii`를 사용하여 투명한 BOM(`\ufeff`) 바이트가 삽입되지 않도록 원천 차단해야 합니다.
- **규칙 2 (소비 측면)**: 파이썬 등 코드 내부에서 설정이나 식별 파일을 읽을 때는 `strip()` 처리뿐만 아니라, `content.startswith('\ufeff')`를 명시적으로 검사하여 BOM을 잘라내는(`content[1:]`) 이중 방어 로직을 무조건 탑재해야 합니다.
- **사유**: BOM 바이트가 포함된 파일 내용을 문자열로 비교할 경우(`content == "PRO_CAFECRAWLER"`), 눈에 보이지 않는 바이트 차이로 인해 조건문이 `False`로 떨어져 앱이 엉뚱한 제품명으로 폴백(Fallback)되거나 비정상 작동하게 됩니다.

### 4.4. 플랜 등급 명칭 및 순서 크몽 표준화 (Standardization Rule)
- **규칙**: 하위 프로그램 및 어드민 대시보드의 서비스 이용 플랜 명칭 및 셀렉트 순서는 크몽(Kmong) 표준 단계를 엄격히 준수합니다.
  1. **STANDARD**: 1개월 이용권 (기본 무제한형)
  2. **DELUXE**: 1개월 이용권 (수집 건수 한도 제한형, 예: 1,000건 제한)
  3. **PREMIUM**: 3개월 이용권 (장기 할인/고급형)
- **사유**: 서비스 채널(크몽 등)과 어드민/프로그램 간 등급 명칭이나 순서가 다를 경우 고객과 관리자 모두에게 혼선을 주게 되므로, 크몽 기준(`STANDARD` ➔ `DELUXE` ➔ `PREMIUM`)으로 완전 통일합니다.

### 4.5. 메인 헤더 플랜 및 만료 기간(D-Day) 배지 표기 (UI Visibility Rule)
- **규칙**: 모든 하위 프로그램의 메인 화면 헤더 제목 우측 또는 바로 아래에 현재 사용 중인 라이선스의 **플랜 명칭**과 **만료 기한(D-Day)**을 시각적 배지(Badge) 형태로 명확히 노출해야 합니다.
  - 예시 (정품): `✅ DELUXE (1,000건 제한)` | `📅 만료일: 2026.05.09 (D-20일)`
  - 예시 (체험판): `🔒 무료 체험판 (50건 제한)`
- **사유**: 고객이 본인이 현재 구매한 서비스의 상품 성격과 남은 이용 기간을 프로그램 내에서 바로 직관적으로 파악할 수 있도록 보장합니다.

### 4.6. 크몽 심사 승인 및 표기 금지어 대체 수칙 (Kmong Compliance Rule)
- **규칙**: 크몽 심사 비승인 방지를 위해 썸네일, 제목, 상세설명, 쇼룸, 어드민 문구 작성 시 특정 타사 상표명 및 차단 연상 키워드의 사용을 엄격히 금지하고 표준 대체어를 사용합니다.
  - **네이버 / Naver / N사 / 초록창** ➔ `포털`
  - **스마트스토어 / 스마트팜** ➔ `포털스토어`, `거래플랫폼`, `오픈마켓`
  - **플레이스 / 스마트플레이스 / Place / N플레이스 / place+** ➔ `포털 지도`, `가게 지도`
  - **크롤링 / 스크래핑** ➔ `데이터 추출`, `데이터 분석`, `정보 수집`
  - **크롤러 / 수집기** ➔ `데이터 추출기`, `정보 파서`, `DB 추출 솔루션`
  - **상위 노출 / 연관검색어 / 키워드 자동완성** ➔ `전면 삭제` (인위적 조작 연상 표현 사용 불가)
  - **N로고 및 검색창 이미지** ➔ `전면 삭제 또는 모자이크(블러) 처리`
- **사유**: 플랫폼 이용 약관 및 타사 자산 보호 정책 준수를 통해 심사 비승인 및 서비스 차단을 예방하고 정상 영업 승인을 보장합니다.

### 4.7. 다운로드 URL 브라우저 캐시 방지 필수 수칙 (Cache-Busting Rule)
- **규칙**: 대시보드, 쇼룸, 무상 다운로드 페이지 등 모든 웹 화면에서 프로그램 압축 파일(`releases/latest/download/*.zip`) 링크를 생성할 때는 타임스탬프 쿼리 파라미터(`?t=${Date.now()}`)를 반드시 결합해야 합니다.
- **사유**: 웹 브라우저(크롬/엣지)가 고정된 다운로드 URL에 대해 이전 버전 ZIP 캐시를 로컬에서 재사용하는 현상을 근본 차단함으로써, 구매자가 최신 버전을 새로 다운받았음에도 직후 OTA 업데이트 팝업을 마주치는 혼선 및 어색한 UX를 완전 예방합니다.

### 4.8. 단일 소스 유지보수 & 제품별 패키징 독립 실행 파일명 필수 수칙 (Single Source & Unique Exe Rule)
- **핵심 원칙**: 
  1. **단일 소스 유지보수 (Single Source of Truth)**: 멀티 패키지/라인업을 형성하는 모든 프로그램은 반드시 **단 1개의 소스 리포지토리**에서 통합 개발 및 유지보수하며, PyInstaller 엔진 빌드도 단 1회만 수행합니다. (소스 파편화 절대 엄금)
  2. **독립 실행 파일명 패키징 (Unique Exe Staging)**: 단일 빌드로 생성된 실행 파일을 개별 상품 ZIP으로 최종 스테이징(포장)하는 시점에만, 범용 명칭(`CafeScraper.exe`)이 아닌 각 제품의 전용 명칭(`CafeCrawler.exe`, `EventStats.exe`, `AutoComment.exe`, `CafeMonster-Trial.exe`)으로 이름표를 각각 부여하여 압축합니다.
- **적용 범위**: 향후 개발되는 모든 3Monster 하부 마케팅/커뮤니티/앱 몬스터 솔루션 개발 시 본 패키징 아키텍처 수칙을 100% 공통 적용합니다.
- **사유**: 개발 및 핫픽스 관리의 일원화(Single Repository) 장점은 100% 유지하면서, 다중 상품 구매 고객의 로컬 덮어쓰기 오작동 및 프로그램 구별 혼선 UX 문제를 완벽히 해결합니다.

### 4.9. 멀티 프로덕트 APPDATA 저장소 완전 격리 수칙 (Isolated User Storage Policy)
- **규칙**: 모든 몬스터 계열 프로그램은 `%APPDATA%\MarketingMonster\<제품코드>`(예: `CafeCrawler`, `EventStats`, `AutoComment`, `NPlace-DB` 등) 형식으로 로컬 설정, 라이선스 파일(`license.dat`), 캐시 파일(`license_cache.json`)의 저장 경로를 **제품별로 완벽히 격리**해야 합니다.
- **사유**: 단일 소스 베이스에서 여러 독립 에디션을 파생시킬 때, 고객이 여러 제품을 구매하여 동시에 사용할 경우 시리얼 키나 라이선스 권한이 서로 간섭하거나 덮어씌워지는 오류를 원천 차단합니다.

### 4.10. 로컬 캐시 스키마 무결성 검증 수칙 (Cache Schema Integrity Rule)
- **규칙**: 0.1초 고속 오프라인 실행을 위한 로컬 캐시(`license_cache.json`)를 읽을 때 단순히 파일 존재 및 만료 시간만 검사하지 않고, 필수 필드(`products`, `limits`, `exp_dates`, `license_types`)가 모두 온전히 포함되어 있는지 **스키마 무결성을 반드시 검증**해야 합니다. 구버전 캐시 등으로 필드가 누락된 경우 즉시 캐시를 무효화하고 서버 실시간 재조회를 수행하여 갱신합니다.
- **사유**: 앱 업데이트 이후 이전 버전의 캐시 잔재로 인해 플랜 등급(`PREMIUM`)이나 만료일 정보가 비어 `DELUXE` 등으로 잘못 폴백 되는 현상을 완벽히 방지합니다.

### 4.11. 한국 표준시(KST) 및 달력 월 기준 만료일자 산출 수칙 (KST Calendar Month Expiration Rule)
- **규칙**: 라이선스 첫 실행일 기준 만료일자 자동 산출 시, 단순 일수(+90일 등) 덧셈이 아닌 **정확한 달력 월(Calendar Month) 기준의 1일 전 23:59:59 KST (한국 표준시 UTC+9)**로 계산하여 저장해야 합니다. (예: 8월 24일 첫 실행 시 3개월 만료일은 `2026-11-23 23:59:59 KST` = `2026-11-23T14:59:59Z`).
- **사유**: 31일 달(8월, 10월 등)에 따른 이틀 누락 및 UTC 시차로 인해 웹 대시보드나 앱에서 만료일이 하루 밀려 표시되는 문제를 방지하여 한국인 이용자 정서에 100% 부합하는 투명한 이용 기간을 제공합니다.

### 4.12. 윈도우 네이티브 `tar.exe` 기반 1초대 초고속 OTA 교체 수칙 (Native Tar Fast-Update Rule)
- **규칙**: OTA 자동 업데이트 적용 시 파이썬 내부의 무거운 압축 해제나 느린 `xcopy` 6,000개 파일 루프 복사를 전면 배제하고, 윈도우 10/11 내장 `tar.exe -xf` 명령어를 활용하여 다운로드된 ZIP을 1초 만에 원자적(Atomic)으로 직접 교체하고 즉시 새 프로세스를 시작하도록 구성합니다.
- **사유**: 다운로드 완료 후 교체 과정에서 발생하던 15~20초간의 화면 공백 지연을 1초대로 단축하여, 사용자가 프로그램 멈춤으로 오인하고 강제 종료하는 사고를 원천 방지합니다.

### 4.13. 3Monster 브랜드 일체형 Modern OTA 모달 UI 수칙 (Brand-Consistent Modern OTA UI Rule)
- **규칙**: 흰 백지의 구형 OS 기본 팝업(`tkinter.messagebox`)을 일체 배제하고, `CustomTkinter` 기반의 브랜드 다크 모던 테마(450x240, 둥근 카드, 감각적인 블루/스카이 타이포그래피, 인디터미네이트 프로그레스바)로 제작된 전용 모달(`updater_gui.py`)을 띄워야 합니다.
- **사유**: 텍스트 잘림 없는 완벽한 레이아웃과 생동감 있는 다운로드 진행 바, 원터치 자동 재시작 피드백을 통해 고객에게 정돈된 프리미엄 상용 솔루션의 시각적 신뢰감을 제공합니다.

---
*Updated on 2026-08-25 by Antigravity*

