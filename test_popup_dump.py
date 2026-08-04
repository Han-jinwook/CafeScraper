import time
import urllib.parse
from app.products.scraper.crawler import NaverCafeCrawler

c = NaverCafeCrawler()
c.start_browser()

# Log in using the crawler's method
print("Logging in...")
c.driver.get('https://nid.naver.com/nidlogin.login')
time.sleep(3)
input("Please log in manually on the browser, then press Enter here: ")

club_id = "10010818" # Logout cafe
nick = "날아날아"
encoded_nick = urllib.parse.quote(nick)

url = f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0?viewType=L&ta=WRITER&page=1&q={encoded_nick}"
print("Visiting:", url)
c.driver.get(url)
time.sleep(5)

# Try clicking
click_js = f"""
let a_tags = document.querySelectorAll('a, div, span, button');
for (let i = 0; i < a_tags.length; i++) {{
    let el = a_tags[i];
    let text = (el.textContent || '').trim();
    let cl = el.getAttribute('class') || '';
    if (text.indexOf('{nick}') > -1 || text === '{nick}') {{
        let oc = el.getAttribute('onclick') || '';
        if (oc.indexOf('ui(') > -1) {{
            el.click();
            return "OK_UI";
        }}
        if (cl.indexOf('nickname') > -1 || cl.indexOf('nick_btn') > -1) {{
            el.click();
            return "OK_CLASS";
        }}
    }}
}}
return "NOT_FOUND";
"""
res = c.driver.execute_script(click_js)
print("Click result:", res)

time.sleep(3) # Wait for popup

# Dump HTML
with open('logs/popup_dump.html', 'w', encoding='utf-8') as f:
    f.write(c.driver.page_source)
print("Dumped logs/popup_dump.html")

c.driver.quit()
