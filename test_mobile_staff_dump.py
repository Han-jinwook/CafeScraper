from app.products.scraper.crawler import NaverCafeCrawler
import time
import json
import re

c = NaverCafeCrawler()
c.start_browser()

# Start intercepting
c.driver.execute_cdp_cmd('Network.enable', {})

script = """
window._intercepted = [];
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    window._intercepted.push(args[0]);
    return originalFetch.apply(this, args);
};
"""
c.driver.get("https://m.cafe.naver.com")
c.driver.execute_script(script)

# Navigate
c.driver.get("https://m.cafe.naver.com/ca-fe/cafes/29417622/members/staff")
time.sleep(5)

# dump the HTML to see if there is __NEXT_DATA__
src = c.driver.page_source
with open("logs/mobile_staff_dump.html", "w", encoding="utf-8") as f:
    f.write(src)

# also check for __NEXT_DATA__
try:
    print('NEXT_DATA tag count:', src.count('__NEXT_DATA__'))
except:
    pass

c.driver.quit()
