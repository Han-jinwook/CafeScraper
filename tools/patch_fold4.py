import sys

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Update CSS to remove margin and make it fit perfectly
css_start = -1
css_end = -1
for i, line in enumerate(lines):
    if 'st.markdown(\'\'\'' in line and '<style>' in lines[i+1]:
        css_start = i
    if css_start != -1 and '\'\'\', unsafe_allow_html=True)' in line:
        css_end = i
        break

if css_start != -1:
    new_css = """st.markdown('''
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
        margin-top: 0 !important;
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
    lines[css_start:css_end+1] = [new_css]

# Re-read lines as string to do string replacements
content = "".join(lines)

# --- Fix _t1 ---
# Find the button in t1
t1_btn_str = '        if st.button("🔍 게시판 목록 가져오기", help="현재 열린 카페 화면에서 모든 게시판 목록을 스캔합니다.", width="stretch"):\n'
t1_btn_new = """        c_scan, c_tog1 = st.columns([0.9, 0.1])
        with c_tog1:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)
        with c_scan:
            if st.button("🔍 게시판 목록 가져오기", help="현재 열린 카페 화면에서 모든 게시판 목록을 스캔합니다.", width="stretch"):
"""
content = content.replace(t1_btn_str, t1_btn_new)

# Remove t1 middle section
t1_mid_old = """    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c1, _c2 = st.columns([0.85, 0.15])
    with _c1:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c2:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
"""
t1_mid_new = """        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
"""
content = content.replace(t1_mid_old, t1_mid_new)

# --- Fix _t2 ---
t2_btn_str = """        col1, col2 = st.columns(2)
        start_date = col1.date_input("시작일", default_start)
        end_date = col2.date_input("종료일", default_end)"""
t2_btn_new = """        col1, col2, col_tog2 = st.columns([0.45, 0.45, 0.1])
        start_date = col1.date_input("시작일", default_start)
        end_date = col2.date_input("종료일", default_end)
        with col_tog2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_2", on_click=toggle_settings)"""
content = content.replace(t2_btn_str, t2_btn_new)

t2_mid_old = """    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c3, _c4 = st.columns([0.85, 0.15])
    with _c3:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c4:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_2", on_click=toggle_settings)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
"""
t2_mid_new = """        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
"""
content = content.replace(t2_mid_old, t2_mid_new)


# --- Fix _t3 ---
t3_btn_str = """        st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
        st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")"""
t3_btn_new = """        st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
        c_cap, c_tog3 = st.columns([0.9, 0.1])
        with c_cap:
            st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
        with c_tog3:
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)"""
content = content.replace(t3_btn_str, t3_btn_new)

t3_mid_old = """    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c5, _c6 = st.columns([0.85, 0.15])
    with _c5:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c6:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
"""
t3_mid_new = """        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
"""
content = content.replace(t3_mid_old, t3_mid_new)

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
