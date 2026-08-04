import sys
import requests, re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = 'https://m.cafe.naver.com/campingfirst'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'})
js_files = re.findall(r'src="(https://[^"]+\.js)"', r.text)
# Also check for relative JS files
js_files += re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', r.text)

print('Found JS files:', len(js_files))

for js in set(js_files):
    if js.startswith('/'):
        js = 'https://m.cafe.naver.com' + js
    try:
        content = requests.get(js, headers={'User-Agent': 'Mozilla/5.0'}).text
        if 'graphql' in content.lower() or 'query' in content.lower():
            queries = re.findall(r'(query\s+[a-zA-Z0-9_]+\s*\{[^}]+\})', content)
            if queries:
                print(f'Found queries in {js}:')
                for q in set(queries):
                    print(q)
            
            if 'bff.cafe' in content:
                print(f'Found bff in {js}!')
                idx = content.find('bff.cafe')
                print(content[max(0, idx-100):min(len(content), idx+500)])
    except Exception as e:
        pass
print('Done parsing JS files')
