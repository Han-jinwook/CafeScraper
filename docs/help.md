# 인수인계 메모 (2026-04-30 최종)

## 대상

- 기능: `pages/04_auto_commenter.py` (자동 댓글러)
- 관련 로직:
  - UI/플로우: `pages/04_auto_commenter.py`
  - 댓글 실행: `app/products/commenter/bot.py`
  - 타겟 스냅샷 DB: `app/utils/event_db.py` (`commenter_targets`)

---

## 핵심 이슈: 1순위 원인 판단

### 증상

```
[commenter/write] 입력창 셀렉터: .comment_inbox_text
[commenter/write] 붙여넣기 후 입력 길이=0 미리보기=''
```

- DOM에서 `.comment_inbox_text`는 잡히지만, 붙여넣기/JS 주입/send_keys 모두 길이 0.
- "요소를 못 찾았다"가 아니라, **찾은 요소에 값을 넣어도 네이버 에디터 내부 상태가 안 바뀜**.

### 유력 원인

> `.comment_inbox_text`는 "보이는 댓글창 영역"일 뿐, 실제 텍스트가 들어가는 editable root가 아닐 가능성이 가장 높다.

네이버 최신 에디터 특성:
- `input`/`textarea`가 아닌 `contenteditable` div/span 구조
- React류 프론트: 단순 DOM 값 변경만으로 내부 상태 갱신 안 됨
- SyntheticEvent가 감싸므로 브라우저 이벤트만으로 앱 상태 반영 안 될 수 있음

### 결론

> 지금 문제는 "댓글 문구" 문제가 아니라 **"입력 sink 탐색 + 에디터 이벤트 반영"** 문제다.

---

## 해결 방향: write_comment() 재설계

### 기존 흐름 (실패)

```
.comment_inbox_text 찾기 → paste → 길이=0 → fallback → 그래도 0 → fail
```

### 신규 흐름

```
댓글 영역 클릭
→ 실제 입력 후보 전체 탐색 (iframe 포함)
→ 후보별 입력 시도 (send_keys → paste → execCommand → JS injection)
→ 입력 반영 검증
→ 성공한 후보로 등록 버튼 클릭
→ 댓글 DOM 반영 확인
→ success/fail 기록
```

### 입력 후보 탐색 순서

1. iframe 내부까지 순회
2. `textarea`
3. `input[type=text]`
4. `[contenteditable="true"]`
5. `[role="textbox"]`
6. `.comment_inbox_text` 하위의 contenteditable 요소
7. 클릭 후 `activeElement` 또는 activeElement의 상위 contenteditable 요소

### 입력 방식 우선순위

| 순위 | 방식 | 비고 |
|------|------|------|
| 1 | click + send_keys | 가장 인간적, contenteditable에 잘 먹음 |
| 2 | clipboard paste (Ctrl+V) | 포커스가 올바르면 유효 |
| 3 | `execCommand("insertText")` | 구형이지만 에디터에서 의외로 유효 |
| 4 | native value setter + input/change event | textarea/input용 |
| 5 | innerText/textContent + beforeinput/input/keydown/keyup/blur | contenteditable용 |

### 입력 검증

- `input`/`textarea`: `.value` 길이
- `contenteditable`: `innerText` 또는 `textContent` 길이
- 길이 0이면 절대 등록 버튼 클릭하지 않음

### 등록 후 성공 판정

```python
def is_comment_posted(driver, comment_text):
    short = comment_text[:20]
    xpath = f"//*[contains(normalize-space(.), {repr(short)})]"
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
```

- 등록 버튼 클릭 = success 처리 제거
- 댓글 목록 DOM에 방금 입력한 본문 일부 출현 확인 후 success

### 실패 로그 필수 항목

- 찾은 후보 셀렉터, tagName, contenteditable 여부, role, className
- activeElement 정보, iframe 내부 여부
- 입력 방식별 결과 길이

---

## 진단용 JS (후보 탐색 스크립트)

```javascript
(() => {
  const candidates = [];
  const push = (el, reason) => {
    if (!el) return;
    candidates.push({
      reason, tag: el.tagName, id: el.id, className: el.className,
      role: el.getAttribute("role"),
      contenteditable: el.getAttribute("contenteditable"),
      isContentEditable: el.isContentEditable,
      text: (el.innerText || el.textContent || el.value || "").slice(0, 80)
    });
  };
  document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]').forEach(el => push(el, "global"));
  document.querySelectorAll('.comment_inbox_text').forEach(box => {
    push(box, ".comment_inbox_text");
    box.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]').forEach(el => push(el, "inside-comment_inbox_text"));
  });
  push(document.activeElement, "activeElement");
  return candidates;
})();
```

---

## 상태머신 (UI 버튼 활성 규칙)

```python
COMMENTER_STATE = {
    "idle": "초기 상태",
    "browser_ready": "브라우저 열림",
    "collecting": "타겟 수집 중",
    "ready": "타겟 수집 완료",
    "running": "댓글 작성 중",
    "stopping": "중지 요청됨",
    "paused": "중지됨",
    "done": "완료",
    "error": "오류",
}
```

| 상태 | 허용 동작 |
|------|-----------|
| idle/browser_ready | 수집 가능 |
| collecting | 모든 실행 버튼 잠금 |
| ready/paused/done | 댓글 시작 가능 |
| running/stopping | 중지만 가능 |
| error | 재시작 가능 |

---

## Streamlit removeChild 문제 (후순위)

- 서버 에러가 아닌 클라이언트 DOM 갱신 이슈
- 우회: `st.empty()` 고정 placeholder, 동적 위젯 최소화, 갱신 간격 제한
- 입력 문제 해결 후 안정화 단계에서 처리

---

## 일시중지 / 재시도 운영 규칙

### 일시중지
- `⏹ 댓글 작성 중지`는 현재 글 1건 완료 후 다음 루프 진입 전에 멈춤
- 즉시 하드 인터럽트가 아님 → 로그가 잠시 더 나올 수 있음

### 다시 하고 싶을 때
- 별도 "재시작" 버튼 없음. 그냥 `🚀 댓글 작성 시작` 다시 누르면 됨
- 타겟 목록은 DB에 영구 저장되므로 새로고침해도 유지됨

### 처음부터 다시 (타겟 재수집)
- `2단계: 타겟 목록 수집` 재실행

---

## 참고

- 2026-04-09 `03_event_comment_lottery` 관련 메모는 별도 브랜치/히스토리 참고.
