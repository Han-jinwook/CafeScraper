import requests
import re
res = requests.get('https://ca-fe.pstatic.net/web-mobile/js/app.9e2e5c88cc92.js')
urls = re.findall(r'"(/cafe-[^"]+)"', res.text)
for u in set(urls):
    if 'member' in u.lower() or 'staff' in u.lower() or 'leader' in u.lower():
        print(u)
