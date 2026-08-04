import time
import urllib.parse
from app.products.scraper.crawler import NaverCafeCrawler
from selenium.webdriver.common.by import By

crawler = NaverCafeCrawler(debug_mode=True)
crawler.start_browser()

keyword = "캠핑"
encoded_keyword = urllib.parse.quote(keyword)
search_url = f"https://section.cafe.naver.com/ca-fe/home/search/cafes?query={encoded_keyword}"
print("Navigating to:", search_url)
crawler.driver.get(search_url)

try:
    time.sleep(6.0)
    print("Page source length:", len(crawler.driver.page_source))
    
    # Let's search for actual cafe links
    links = crawler.driver.find_elements(By.TAG_NAME, "a")
    found = []
    for link in links:
        try:
            href = link.get_attribute("href") or ""
            text = link.text or ""
            if "cafe.naver.com" in href:
                found.append((text.strip(), href.strip()))
        except:
            pass
    print("Found actual cafe links:")
    for f in found:
        print(f"Text: {f[0]} | URL: {f[1]}")

except Exception as e:
    print("Error:", e)
finally:
    crawler.close()
