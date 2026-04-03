import sys

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

t3_old = """            st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
            st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
        except:
            st.info("DB 통계를 읽을 수 없습니다.")"""

t3_new = """            c_cap, c_tog3 = st.columns([0.9, 0.1])
            with c_cap:
                st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
                st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
            with c_tog3:
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)
        except:
            c_info, c_tog3 = st.columns([0.9, 0.1])
            with c_info:
                st.info("DB 통계를 읽을 수 없습니다.")
            with c_tog3:
                st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)"""

content = content.replace(t3_old, t3_new)

# Also remove the leftover old t3 button that wasn't removed properly
t3_mid_old = """    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
    _c5, _c6 = st.columns([0.85, 0.15])
    with _c5:
        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;'>상세 설정</div>", unsafe_allow_html=True)
    with _c6:
        st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):"""

t3_mid_new = """        if not st.session_state.settings_collapsed:"""
content = content.replace(t3_mid_old, t3_mid_new)

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
