import sys
import requests, re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = 'https://cafe.naver.com/campingfirst'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
js_files = re.findall(r'src="(https://[^"]+\.js)"', r.text)
print('Found JS files:', len(js_files))

for js in js_files:
    if 'cafe' in js or 'main' in js:
        try:
            content = requests.get(js).text
            if 'graphql' in content.lower() or 'query' in content.lower():
                queries = re.findall(r'(query\s+[a-zA-Z0-9_]+\s*\{[^}]+\})', content)
                if queries:
                    print(f'Found queries in {js}:')
                    for q in set(queries):
                        print(q)
                
                # Also check for bff
                if 'bff.cafe' in content:
                    print(f'Found bff in {js}!')
                    # print nearby text
                    idx = content.find('bff.cafe')
                    print(content[max(0, idx-100):min(len(content), idx+500)])
        except Exception as e:
            pass
print('Done parsing JS files')
