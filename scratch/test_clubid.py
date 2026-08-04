import requests, re
url = 'https://cafe.naver.com/sundreamd'
r = requests.get(url)
m = re.search(r'clubid\s*=\s*[\"\']?(\d+)', r.text, re.I) or re.search(r'clubId\s*:\s*[\"\']?(\d+)', r.text, re.I)
print(m.group(1) if m else 'Not found')
