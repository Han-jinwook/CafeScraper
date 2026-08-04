import requests, re
res = requests.get('https://m.cafe.naver.com/ca-fe/cafes/10010818')
m = re.search(r'"manager"\s*:\s*\{[^}]*\}', res.text)
if m:
    print('Found manager in main page:', m.group(0))
else:
    print('Not found in main page')
