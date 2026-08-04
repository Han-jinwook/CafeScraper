from bs4 import BeautifulSoup
import re
with open('logs/my_test_spa_search.html', 'r', encoding='utf-8') as f:
    html = f.read()
soup = BeautifulSoup(html, "html.parser")
# Find links to member profiles
a_tags = soup.find_all("a", href=True)
for a in a_tags:
    if "memberKey=" in a["href"]:
        print(a["href"])
        print(a.text)
