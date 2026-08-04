import sys
import requests, re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

r = requests.get('https://m.cafe.naver.com/campingfirst', headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)'})
print('Length:', len(r.text))
build_id = re.search(r'"buildId":"([^"]+)"', r.text)
if build_id:
    print('Found Build ID:', build_id.group(1))
else:
    print('No buildId found')
