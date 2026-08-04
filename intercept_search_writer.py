import urllib.parse
from app.products.scraper.crawler import NaverCafeCrawler
import time

c = NaverCafeCrawler()
c.start_browser()

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
encoded_nick = urllib.parse.quote(nick)

c.driver.get(f"https://cafe.naver.com/ArticleList.nhn?search.clubid={club_id}")
time.sleep(2)
c.driver.execute_script(script)

# Navigate via router to preserve window state (but window.location reloads...)
# Let's just load the SPA URL directly, and use a MutationObserver to grab fetch? No, if we reload, the interceptor is lost.
# Instead, let's use the Performance API AGAIN, because it works across reloads!
c.driver.get(f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0?viewType=L&ta=WRITER&page=1&q={encoded_nick}")
time.sleep(6) # wait for SPA

resources = c.driver.execute_script("""
return window.performance.getEntriesByType('resource').map(r => r.name);
""")

for r in resources:
    if "api" in r or "search" in r or "json" in r or "graphql" in r:
        print(r)

c.driver.quit()
