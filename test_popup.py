from app.products.scraper.crawler import NaverCafeCrawler
import time
import urllib.parse
from bs4 import BeautifulSoup

c = NaverCafeCrawler()
c.start_browser()

club_id = "29417622"
nick = "캠핑퍼스트"
encoded_nick = urllib.parse.quote(nick)

url = f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0?viewType=L&ta=WRITER&page=1&q={encoded_nick}"
c.driver.get(url)
time.sleep(5)

# Click the nickname using JS
click_js = """
let nicks = document.querySelectorAll('.writer_info .nickname');
if (nicks.length > 0) {
    nicks[0].click();
    return true;
}
return false;
"""
clicked = c.driver.execute_script(click_js)
print("Clicked:", clicked)

if clicked:
    time.sleep(2)
    # Dump HTML to find the popup layer!
    with open('logs/popup_test.html', 'w', encoding='utf-8') as f:
        f.write(c.driver.page_source)
    print("Saved popup_test.html")

c.driver.quit()
