import requests
import re
res = requests.get('https://ca-fe.pstatic.net/web-mobile/js/app.9e2e5c88cc92.js')
urls = re.findall(r'"([^"]*?(?:Info|Profile|Member|Staff).*?\.json)"', res.text, re.IGNORECASE)
for u in set(urls):
    print(u)
