import urllib.parse
from app.products.scraper.crawler import NaverCafeCrawler
import time
import json

c = NaverCafeCrawler()
c.start_browser()

# Enable Network tracking via CDP
c.driver.execute_cdp_cmd('Network.enable', {})

# We need to capture requests. The simplest way in undetected_chromedriver without complex CDP listeners 
# is to use driver.get_log('performance'). But it might not be enabled.
# Let's inject a fetch interceptor directly into the page BEFORE it loads? No, we can just inject it and then trigger a search.

script = """
window._intercepted = [];
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    window._intercepted.push(args[0]);
    return originalFetch.apply(this, args);
};
"""

club_id = "29417622"
nick = "캠핑퍼스트"
encoded_nick = urllib.parse.quote(nick.encode('utf-8'))
# Load a dummy page in the cafe first to inject the script
c.driver.get(f"https://cafe.naver.com/ArticleList.nhn?search.clubid={club_id}")
time.sleep(2)
c.driver.execute_script(script)

# Navigate via JS so the window is not reloaded? No, Vue SPA is at /f-e/cafes.
# If we change window.location.href, the page reloads, and our interceptor is lost.
# But wait! If we just load the SPA, and THEN inject the interceptor, and THEN click a pagination button?
# Or just use driver.requests from selenium-wire? We don't have selenium-wire.

# Let's just use the Performance timing API to get resource URLs!
c.driver.get(f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0?viewType=L&ta=ARTICLE_COMMENT&page=1&q={encoded_nick}")
time.sleep(5)

resources = c.driver.execute_script("""
return window.performance.getEntriesByType('resource').map(r => r.name);
""")

for r in resources:
    if "api" in r or "search" in r or "json" in r or "graphql" in r:
        print(r)

c.driver.quit()
