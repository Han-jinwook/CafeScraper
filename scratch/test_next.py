import json
import re

with open('logs/mobile_info_next_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

text = json.dumps(data, ensure_ascii=False)
matches = re.finditer(r'"nickname"\s*:\s*"([^"]+)"[^}]*?"memberKey"\s*:\s*"([^"]+)"', text)
for m in matches:
    print('Found staff:', m.group(1), m.group(2))
