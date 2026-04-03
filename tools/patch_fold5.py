import sys

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = """        c_scan, c_tog1 = st.columns([0.9, 0.1])
        with c_tog1:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)
        with c_scan:
            if st.button("🔍 게시판 목록 가져오기", help="현재 열린 카페 화면에서 모든 게시판 목록을 스캔합니다.", width="stretch"):"""

good_str = """        c_scan, c_tog1 = st.columns([0.9, 0.1])
        with c_tog1:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)
        
        scan_clicked = c_scan.button("🔍 게시판 목록 가져오기", help="현재 열린 카페 화면에서 모든 게시판 목록을 스캔합니다.", use_container_width=True)
        if scan_clicked:"""

content = content.replace(bad_str, good_str)

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
