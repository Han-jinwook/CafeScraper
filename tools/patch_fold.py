import re

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add toggle state before _t1, _t2, _t3
state_code = """
if "settings_collapsed" not in st.session_state:
    st.session_state.settings_collapsed = False

def toggle_settings():
    st.session_state.settings_collapsed = not st.session_state.settings_collapsed

st.markdown("#### ⚙️ 수집 설정")
"""
content = content.replace('st.markdown("#### ⚙️ 수집 설정")', state_code)

# 2. Patch _t1
t1_split_str = '    with st.container(border=True):\n        st.markdown("##### 📋 게시판 선택 · 수집 대상")'
t1_button_code = """
    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_1", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
            st.markdown("##### 📋 게시판 선택 · 수집 대상")
"""
content = content.replace(t1_split_str, t1_button_code.lstrip('\n'))

# Indent the rest of _t1 bottom container
# Find where _t2 starts
t2_start_idx = content.find('with _t2:')
t1_bottom_start_idx = content.find('st.markdown("##### 📋 게시판 선택 · 수집 대상")')

t1_bottom_code = content[t1_bottom_start_idx:t2_start_idx]
# We need to indent t1_bottom_code by 4 spaces.
# But wait, we only need to indent the lines inside the `with st.container(border=True):` block.
# Actually, it's easier to just do a regex replace for the indentation.
# Let's do it carefully.
lines = t1_bottom_code.split('\n')
indented_lines = []
for line in lines:
    if line.strip() == '':
        indented_lines.append(line)
    else:
        indented_lines.append('    ' + line)
content = content[:t1_bottom_start_idx] + '\n'.join(indented_lines) + content[t2_start_idx:]

# 3. Patch _t2
# Refresh content variables
t2_split_str = '    with st.container(border=True):\n        st.markdown("##### 🔧 작업 모드 · 저장")'
t2_button_code = """
    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_2", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
            st.markdown("##### 🔧 작업 모드 · 저장")
"""
content = content.replace(t2_split_str, t2_button_code.lstrip('\n'))

t3_start_idx = content.find('with _t3:')
t2_bottom_start_idx = content.find('st.markdown("##### 🔧 작업 모드 · 저장")')

t2_bottom_code = content[t2_bottom_start_idx:t3_start_idx]
lines = t2_bottom_code.split('\n')
indented_lines = []
for line in lines:
    if line.strip() == '':
        indented_lines.append(line)
    else:
        indented_lines.append('    ' + line)
content = content[:t2_bottom_start_idx] + '\n'.join(indented_lines) + content[t3_start_idx:]

# 4. Patch _t3
# t3 needs to be split
t3_split_str = '        col_db1, col_db2 = st.columns(2)'
t3_button_code = """
    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_3", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
            col_db1, col_db2 = st.columns(2)
"""
content = content.replace(t3_split_str, t3_button_code.lstrip('\n'))

main_start_idx = content.find('col_main = st.container()')
t3_bottom_start_idx = content.find('col_db1, col_db2 = st.columns(2)')

t3_bottom_code = content[t3_bottom_start_idx:main_start_idx]
lines = t3_bottom_code.split('\n')
indented_lines = []
for line in lines:
    if line.strip() == '':
        indented_lines.append(line)
    else:
        indented_lines.append('    ' + line)
content = content[:t3_bottom_start_idx] + '\n'.join(indented_lines) + content[main_start_idx:]

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
