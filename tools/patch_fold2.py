import sys

with open('D:/CafeScraper/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Add state
for i, line in enumerate(lines):
    if 'st.markdown("#### ⚙️ 수집 설정")' in line:
        state_code = """
if "settings_collapsed" not in st.session_state:
    st.session_state.settings_collapsed = False

def toggle_settings():
    st.session_state.settings_collapsed = not st.session_state.settings_collapsed

"""
        lines.insert(i, state_code)
        break

# Find boundaries
t1_idx = -1
t2_idx = -1
t3_idx = -1
main_idx = -1

for i, line in enumerate(lines):
    if line.startswith('with _t1:'): t1_idx = i
    if line.startswith('with _t2:'): t2_idx = i
    if line.startswith('with _t3:'): t3_idx = i
    if line.startswith('col_main = st.container()'): main_idx = i

# Process T1
t1_bottom_idx = -1
for i in range(t1_idx, t2_idx):
    if 'st.markdown("##### 📋 게시판 선택 · 수집 대상")' in line:
        pass # wait, need to find the container
for i in range(t1_idx, t2_idx):
    if 'st.markdown("##### 📋 게시판 선택 · 수집 대상")' in lines[i]:
        # The container is 1 line above
        if 'with st.container(border=True):' in lines[i-1]:
            t1_bottom_idx = i - 1
            break

# Process T2
t2_bottom_idx = -1
for i in range(t2_idx, t3_idx):
    if 'st.markdown("##### 🔧 작업 모드 · 저장")' in lines[i]:
        if 'with st.container(border=True):' in lines[i-1]:
            t2_bottom_idx = i - 1
            break

# Process T3
t3_bottom_idx = -1
for i in range(t3_idx, main_idx):
    if 'col_db1, col_db2 = st.columns(2)' in lines[i]:
        t3_bottom_idx = i
        break

# Now we need to insert the button and if statement, and indent the rest.
# We must do this from bottom to top so indices don't shift.

# --- T3 ---
t3_button = """    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_3", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
        with st.container(border=True):
"""
lines.insert(t3_bottom_idx, t3_button)
main_idx += 1 # shifted
# Indent from t3_bottom_idx + 1 up to main_idx
for i in range(t3_bottom_idx + 1, main_idx):
    if lines[i].strip():
        lines[i] = '    ' + lines[i]

# --- T2 ---
t2_button = """    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_2", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
"""
lines.insert(t2_bottom_idx, t2_button)
# Indent from t2_bottom_idx + 1 up to t3_idx (which is now shifted)
# Wait, let's recalculate t3_idx
t3_idx = -1
for i in range(len(lines)):
    if lines[i].startswith('with _t3:'):
        t3_idx = i
        break

for i in range(t2_bottom_idx + 1, t3_idx):
    if lines[i].strip():
        lines[i] = '    ' + lines[i]

# --- T1 ---
t1_button = """    st.button("🔽 상세 설정 펼치기" if st.session_state.settings_collapsed else "🔼 상세 설정 접기", key="btn_fold_1", on_click=toggle_settings, use_container_width=True)
    if not st.session_state.settings_collapsed:
"""
lines.insert(t1_bottom_idx, t1_button)
# Recalculate t2_idx
t2_idx = -1
for i in range(len(lines)):
    if lines[i].startswith('with _t2:'):
        t2_idx = i
        break

for i in range(t1_bottom_idx + 1, t2_idx):
    if lines[i].strip():
        lines[i] = '    ' + lines[i]

with open('D:/CafeScraper/app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done")
