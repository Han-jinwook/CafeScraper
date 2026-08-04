import urllib.parse
from app.products.scraper.crawler import NaverCafeCrawler
import time
import json
import re

c = NaverCafeCrawler()
c.start_browser()
# Try SPA search for "캠핑퍼스트" (the manager)
nick = urllib.parse.quote('캠핑퍼스트')
spa_search_url = f"https://cafe.naver.com/f-e/cafes/29417622/menus/0?viewType=L&ta=ARTICLE_COMMENT&page=1&q={nick}"
c.driver.get(spa_search_url)

time.sleep(5) # wait for Vue to render and fetch data
page_src = c.driver.page_source

with open('logs/my_test_spa_search.html', 'w', encoding='utf-8') as f:
    f.write(page_src)
print('Saved my_test_spa_search.html, size:', len(page_src))

# Try to find memberKey in page source
member_keys = re.findall(r'memberKey[\'\"]?\s*:\s*[\'\"]([a-zA-Z0-9_-]+)[\'\"]', page_src, re.IGNORECASE)
if member_keys:
    print('Found memberKeys in HTML:', set(member_keys))
else:
    print('No memberKeys found in HTML directly')

c.driver.quit()
