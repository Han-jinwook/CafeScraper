import json

import streamlit.components.v1 as components


def inject_connect_history_suggestions(
    *,
    prefix: str,
    container_key_fragment: str,
    cafe_names: list[str],
    cafe_urls: list[str],
    name_label: str = "카페명",
    url_label: str = "카페 URL",
    blocked_labels: list[str] | None = None,
) -> None:
    """
    Streamlit text_input에 datalist 기반 입력 이력 추천을 연결한다.
    - prefix: datalist id 충돌 방지용 접두사 (예: "cafe", "event")
    - container_key_fragment: st.container key 일부(예: "settings_card_1")
    """
    names = list(dict.fromkeys([str(x).strip() for x in (cafe_names or []) if str(x).strip()]))[:5]
    urls = list(dict.fromkeys([str(x).strip() for x in (cafe_urls or []) if str(x).strip()]))[:5]
    blocked = blocked_labels or ["네이버 아이디", "네이버 비밀번호"]

    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent && window.parent.document ? window.parent.document : document;
          const names = {json.dumps(names, ensure_ascii=False)};
          const urls = {json.dumps(urls, ensure_ascii=False)};
          const blockedLabels = {json.dumps(blocked, ensure_ascii=False)};
          const nameLabel = {json.dumps(name_label, ensure_ascii=False)};
          const urlLabel = {json.dumps(url_label, ensure_ascii=False)};
          const rootSelector = {json.dumps(f'div[class*="st-key-"][class*="-{container_key_fragment}"]')};

          function esc(s) {{
            return String(s)
              .replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;");
          }}

          function ensureDatalist(id, items) {{
            let dl = doc.getElementById(id);
            if (!dl) {{
              dl = doc.createElement("datalist");
              dl.id = id;
              doc.body.appendChild(dl);
            }}
            dl.innerHTML = (items || []).map(v => `<option value="${{esc(v)}}"></option>`).join("");
          }}

          function byAria(root, ariaLabel) {{
            if (!root) return null;
            return root.querySelector(`input[aria-label="${{ariaLabel}}"]`);
          }}

          function bindList(root, ariaLabel, listId) {{
            const input = byAria(root, ariaLabel);
            if (!input) return;
            input.setAttribute("list", listId);
            input.setAttribute("autocomplete", "on");
          }}

          function disableNativeAutocomplete(root, ariaLabel) {{
            const input = byAria(root, ariaLabel);
            if (!input) return;
            input.removeAttribute("list");
            input.setAttribute("autocomplete", "off");
            input.setAttribute("autocapitalize", "off");
            input.setAttribute("autocorrect", "off");
            input.setAttribute("spellcheck", "false");
          }}

          function applyBindings() {{
            try {{
              const root = doc.querySelector(rootSelector) || doc;
              ensureDatalist("{prefix}_cafe_name_history_list", names);
              ensureDatalist("{prefix}_cafe_url_history_list", urls);
              bindList(root, nameLabel, "{prefix}_cafe_name_history_list");
              bindList(root, urlLabel, "{prefix}_cafe_url_history_list");
              (blockedLabels || []).forEach(lbl => disableNativeAutocomplete(root, lbl));
            }} catch (e) {{
              // no-op: 렌더 타이밍 이슈를 재시도로 흡수
            }}
          }}

          applyBindings();
          [80, 250, 600, 1200].forEach(ms => setTimeout(applyBindings, ms));
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
