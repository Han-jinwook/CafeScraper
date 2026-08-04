from app.products.scraper.crawler import NaverCafeCrawler
import urllib.parse
import time

c = NaverCafeCrawler()
c.start_browser()

# Log in using the cached session
c.driver.get("https://cafe.naver.com/campingfirstcar")
time.sleep(3)

club_id = "29417622"
nick = "캠핑퍼스트"
encoded_nick = urllib.parse.quote(nick)

# Test various parameter combinations for NICKNAME search
tests = [
    f"query={encoded_nick}&searchBy=3",
    f"query={encoded_nick}&searchBy=1",
    f"query={encoded_nick}&searchBy=2",
    f"query={encoded_nick}&target=writer",
    f"query={encoded_nick}&ta=WRITER",
]

for t in tests:
    url = f"https://apis.cafe.naver.com/search/v2/cafes/{club_id}/search/articles?{t}&perPage=15&page=1&menuId=0"
    print(f"Testing: {t}")
    script = f"""
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '{url}', false);
    xhr.withCredentials = true;
    try {{
        xhr.send();
        return xhr.status + '|' + xhr.responseText.substring(0, 500);
    }} catch(e) {{
        return 'ERROR|' + e.message;
    }}
    """
    res = c.driver.execute_script(script)
    print(res)

c.driver.quit()
