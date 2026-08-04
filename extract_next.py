import re
with open('logs/my_test_mobile_staff.html', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.DOTALL)
if m:
    with open('logs/next_data.json', 'w', encoding='utf-8') as fw:
        fw.write(m.group(1))
    print('Saved next_data.json, size:', len(m.group(1)))
else:
    print('Not found')
