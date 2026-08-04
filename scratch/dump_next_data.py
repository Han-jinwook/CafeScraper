import requests, re, json
res = requests.get('https://m.cafe.naver.com/logout', headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36'})
m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', res.text)
if m:
    data = json.loads(m.group(1))
    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
    with open('logs/mobile_main.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
else:
    print('No NEXT_DATA found')
