import re
with open('logs/main_page_top.html', 'r', encoding='euc-kr', errors='ignore') as f:
    text = f.read()
    match = re.search(r'<form name="frmBoardSearch".*?</form>', text, re.IGNORECASE | re.DOTALL)
    if match:
        print(match.group(0))
    else:
        print('Not found')
