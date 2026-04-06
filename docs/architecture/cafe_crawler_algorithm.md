## 목적

- 작성 일시: 2026-02-04 13:09:39
- 최종 업데이트: 2026-03-07 17:33:21

이 문서는 **네이버 카페(PC/SPA 혼재)**에서 안정적으로 “게시글 목록 → 상세(본문/댓글) → 로컬 DB 저장”을 구현하기 위한 **핵심 알고리즘/우회 전략**을 정리한 구현 가이드입니다.
다른 앱/코드베이스에서도 이 문서만 보고 동일한 구조를 빠르게 재현할 수 있도록, 실패 지점과 해결책(우회) 위주로 작성합니다.

---

## 전체 구조(권장 파이프라인)
- **UI/오케스트레이션(예: Streamlit)**: 상태 로그/진행률, 설정 저장, “1단계 브라우저 열기(수동 로그인)” → “2단계 크롤링 시작”
- **브라우저 크롤러(Selenium + undetected-chromedriver)**: 목록/상세 DOM 접근, iframe 전환, URL 정규화, 동적 로딩 대기
- **API 우회(requests)**: 작성자/댓글 ID(고유키) 확보(렌더링 대기 없이 JSON에서 추출)
- **저장소(SQLite)**: `INSERT OR REPLACE`(업서트)로 **스마트 재개(resume)**

---

## DB 스키마(최소)
SQLite 파일 하나(`cafe_data.db`) 안에 여러 테이블 가능.

### posts
- **post_id** TEXT PRIMARY KEY (articleid)
- **member_id** TEXT (작성자 고유키/MemberKey 계열 포함)
- **nickname** TEXT (표시 닉네임)
- **title** TEXT
- **content** TEXT
- **date** TEXT (`YYYY-MM-DD`)
- **board_name** TEXT (게시판명)
- **url** TEXT (원문 URL)

### comments
- comment_id INTEGER PK AUTOINCREMENT
- post_id TEXT FK
- **writer_id** TEXT (댓글 작성자 고유키/MemberKey 계열 포함)
- **nickname** TEXT
- content TEXT
- is_target INTEGER (관계 중심 수집이면 1/0)

**중요**
- “닉네임은 자주 바뀜” → **member_id/writer_id(긴 고유키)를 필수 키로 저장**
- **업서트**: posts는 `INSERT OR REPLACE`, comments는 필요 시 중복 방지를 위해 `(post_id, writer_id, content, ...)` 유니크키 고려

---

## 크롤링 2단계(수동 로그인 전략)
네이버는 캡차/세션보호가 강해 자동 로그인 성공률이 낮음.
따라서 **브라우저를 띄우고 사람이 로그인 확인 후 크롤링**이 가장 안정적.

### 1단계: 브라우저 시작(Visible)
- `undetected-chromedriver` 사용 권장 (탐지 회피)
- 옵션: `--start-maximized`, `--disable-gpu`, `--no-sandbox`, `--disable-dev-shm-usage`
- headless 비권장(차단/구조차이/랜더링 실패 증가)

### 2단계: 목록 → 상세 수집 시작
- 로그인 완료 후 버튼/트리거로 시작
- 크롤링 중간에 “Sorry/차단” 등 나오면 속도 줄이고 재시도/중단

---

## URL 정규화(가장 중요한 포인트 중 하나)
목록에서 잡히는 URL이 `/f-e/ca-fe/...` 같은 **SPA/모바일용**이면,
기존 PC iframe 기반 파서가 길을 잃음.

### 규칙
`https://cafe.naver.com/f-e/cafes/{clubid}/articles/{articleid}...`
→ 아래 PC 표준으로 강제 변환:

`https://cafe.naver.com/ArticleRead.nhn?clubid={clubid}&articleid={articleid}`

### 구현 포인트
- 상세 진입 전에 무조건 `_normalize_article_url()` 적용
- 정규식: `/cafes/(\\d+)/articles/(\\d+)`

---

## iframe 전환(PC 표준 페이지)
PC 표준은 본문이 `iframe#cafe_main` 안에 존재하는 경우가 많음.

### 알고리즘
- `driver.switch_to.default_content()`
- 현재 URL이 `/f-e/` 또는 `/ca-fe/`면 iframe이 없을 수 있으므로 **스킵**
- 아니면 `WebDriverWait(...).until(presence_of_element_located((By.ID,"cafe_main")))`
- `driver.switch_to.frame(iframe)`

**주의**
- iframe 전환 실패/누락은 “본문 요소 미발견”의 1순위 원인

---

## 목록 수집(전체글보기 기준) 알고리즘
목표: 날짜 필터링(`start_date`~`end_date`) 안의 게시글들에 대해
`post_id`, `url`, `title`, `date`, `member_id`, `nickname`, `board_name` 확보.

### 루프
- page=1..N (적당한 상한: 50 또는 설정값)
- 페이지 이동: `driver.get(target_page_url)`
- 스크롤 1회: `execute_script("window.scrollTo(0, 1000);")`
- rows 선택자(사이트 변동 대비 다중):  
  - `"div[class*='ArticleItem'], li[class*='article'], div.article-board table tbody tr"`

### 공지/상단 고정 스킵
- row class에 `notice`, `top` 포함이면 continue

### 날짜 파싱(실패가 잦음)
1) 우선 selector로 찾기:
- `"span[class*='Date']", "span.date", "td.td_date", ".date"`
2) 실패하면 행 텍스트에서 정규식 백업:
- `YYYY.MM.DD` / `MM.DD` / `HH:MM`

### 기간 필터
- `date_val > end_date`면 continue
- `date_val < start_date`면 **더 과거로 갈수록 오래됨** → `should_continue=False`로 루프 종료(성능 최적화)

### 게시판명(board_name) 추출 + 제외 필터
- 후보 selector:
  - `"a.board_name"`, `"td.td_board a"`, `"a[href*='/menus/']"`
- 제외 목록은 **리스트 단계에서 바로 스킵**(상세로 안 들어감)
- 비교는 공백 제거 후 소문자화해서 안정화:
  - `"먹거리 / 맛집"` == `"먹거리/맛집"`

### 작성자(member_id/nickname) 추출(리스트)
닉네임 요소 selector를 여러 개 준비:
- `"a[class*='Nickname']"`, `".nick a"`, `"td.td_name a"`, `"a[class*='Writer']"`, `".writer a"` 등

#### 닉네임 텍스트 추출 팁
SPA에선 `.text`가 비거나 `aria-label`에 군더더기 문구가 붙는 경우가 있음.
- `.text` → `textContent`/`innerText`/`title`/`aria-label` 순으로 폴백
- `"X 님의 게시글 더보기"` 같은 군더더기는 정규화로 제거

---

## “고유키(member_id/writer_id)” 추출: 하이브리드 3단계
네이버가 짧은 ID 대신 **긴 MemberKey**를 쓰는 경우가 많음.
길어도 괜찮고(오히려 불변/유일), 이 값을 저장하면 닉네임 변경에도 추적이 가능함.

### 0) 기본: 요소 속성에서 정규식 추출
- `onclick`/`href`/`data-*` 속성에서 `memberId/memberid/...` 패턴 파싱
- 가장 싸고 빠르지만 최신 SPA에선 비어있을 수 있음

### 1) UI 레이어 우회(닉네임 클릭)
- 닉네임 클릭 → 작성자 레이어(팝업) 뜨면, 내부 링크 `blogId=...` 또는 `memberId=...` 파싱
- 클릭 실패/레이어 미노출 케이스 많으므로 “fallback”로 사용

### 2) API 우회(가장 확실/추천)
#### 게시글 작성자
- `clubid`, `articleid`를 확보한 뒤:
  - `https://apis.naver.com/cafe-web/cafe-article/v1/articles/{articleid}?useCafeId=false&buid={clubid}`
- 응답 JSON에서 `result.article.writer`의 `id/memberKey/memberId/...`를 탐색해 저장
- **닉네임도 같이** `nickname/nickName/displayName/...`를 탐색해 저장(목록에서 unknown인 경우 보강)

#### 댓글 목록
- **CommentView JSON**을 우선 시도:
  - `https://cafe.naver.com/CommentView.nhn?search.clubid={clubid}&search.articleid={articleid}`
- JSON 또는 JSONP로 올 수 있어 파싱 방어 필요
- 댓글 항목의 `writerId/memberKey/userKey/...` 후보군에서 writer_id 추출

### 3) JS 전역상태(최후 수단)
- `window.__INITIAL_STATE__`/`__NEXT_DATA__` 등에서 writer id 탐색
- 구조가 계속 바뀌므로 추천도는 낮고, 디버그/백업에 적합

---

## 상세 수집(본문 + 댓글) 알고리즘
### 상세 진입
- `article_url = normalize(article_url)`
- `driver.get(article_url)`
- iframe 필요 시 전환

### 본문 추출
선택자 다중 준비(에디터 버전/SPA 변화 대응):
- `.se-main-container`
- `div[class*='ArticleContentBox']`
- `#articleBody`
- `div.article_viewer`

### 치유일기 고정 안내문 제거(옵션)
- 본문 앞부분에서 특정 키워드 조합이 감지될 때만 제거(오탐 방지)
- 문자열 탐색/슬라이싱이라 부담 거의 없음

### 댓글 수집(관계 중심 필터링 예시)
- 기본은 `CommentView` JSON으로 가져오는 것이 안정적
- 관계 중심이면:
  - `writer_id == post_author_id` 또는 `nickname in admin_nicks`만 저장

---

## 속도/차단 방지(운영 팁)
- 목록 페이지 사이: `random.uniform(3,6)` 같은 랜덤 딜레이
- 상세 게시글 사이: `random.uniform(3,7)` 정도
- API 요청은 0.3~0.8s 정도로도 충분하지만, 429/5xx시 **지수 백오프 재시도**
- “0개 수집/멈춤”이면:
  - URL 정규화 누락, iframe 전환 실패, 날짜 파싱 실패, 차단 페이지(“Sorry”)를 먼저 의심

---

## 스마트 재개(resume)
- 목록 단계에서 URL만 긁고, 상세 저장 전에 DB에 `post_id`가 있으면 skip
- 게시글은 `INSERT OR REPLACE`로 언제든 갱신 가능(닉네임/board_name/본문 보강)

---

## 구현 체크리스트(실전)
- [ ] `/f-e/` URL을 `ArticleRead.nhn`로 정규화했는가?
- [ ] iframe `cafe_main` 전환 로직이 SPA/PC 모두 안전한가?
- [ ] 작성자/댓글 고유키를 **API 우회로 확보**하는가?
- [ ] 게시판명(`board_name`)을 목록에서 추출하고, 제외 목록을 목록 단계에서 필터링하는가?
- [ ] 날짜 파싱 실패 시 정규식 백업이 있는가?
- [ ] 랜덤 딜레이 + 재시도/백오프가 있는가?
- [ ] DB 업서트 + skip으로 재개가 가능한가?

---

## “독립 UI” 제안(권장 형태)
한 화면에서 두 작업이 섞이면 사용자가 헷갈림.
- 탭/페이지를 분리:
  - `네이버 카페 수집` 탭: 1단계/2단계 + 로그 + posts/comments 관리
  - `논문(위키) 수집` 탭: 시작 URL/딜레이/진행 카운트 + papers 관리

