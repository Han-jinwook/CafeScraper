import sys

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

css_code = """
st.markdown('''
    <style>
    /* 투명하고 작은 우측 화살표 버튼 스타일 */
    div[class*="st-key-btn_fold_"] button {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        color: #94a3b8 !important;
        padding: 0 !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.5 !important;
        display: flex;
        justify-content: flex-end;
    }
    div[class*="st-key-btn_fold_"] button:hover {
        color: #334155 !important;
        background: transparent !important;
    }
    div[class*="st-key-btn_fold_"] p {
        font-size: 1.1rem !important;
        margin: 0 !important;
    }
    </style>
''', unsafe_allow_html=True)
"""

content = content.replace(
    "def toggle_settings():\n    st.session_state.settings_collapsed = not st.session_state.settings_collapsed\n",
    "def toggle_settings():\n    st.session_state.settings_collapsed = not st.session_state.settings_collapsed\n" + css_code
)

old_btn_1 = '    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_1", on_click=toggle_settings, use_container_width=True)'
new_btn_1 = '''    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c1, _c2 = st.columns([0.85, 0.15])
    with _c1:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c2:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)'''
content = content.replace(old_btn_1, new_btn_1)

old_btn_2 = '    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_2", on_click=toggle_settings, use_container_width=True)'
new_btn_2 = '''    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c3, _c4 = st.columns([0.85, 0.15])
    with _c3:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c4:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_2", on_click=toggle_settings)'''
content = content.replace(old_btn_2, new_btn_2)

old_btn_3 = '    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_3", on_click=toggle_settings, use_container_width=True)'
new_btn_3 = '''    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c5, _c6 = st.columns([0.85, 0.15])
    with _c5:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c6:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)'''
content = content.replace(old_btn_3, new_btn_3)

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
