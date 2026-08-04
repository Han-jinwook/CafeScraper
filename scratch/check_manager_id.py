import requests, re
res = requests.get('https://cafe.naver.com/logout', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
m = re.search(r'"managerId":"(.*?)"', res.text)
if m:
    print('Manager ID (managerId):', m.group(1))
m2 = re.search(r'"managerMemberKey":"(.*?)"', res.text)
if m2:
    print('Manager MemberKey (managerMemberKey):', m2.group(1))
