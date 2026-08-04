import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import time
from app.products.scraper.crawler import NaverCafeCrawler
from selenium.webdriver.common.by import By

crawler = NaverCafeCrawler(debug_mode=True)
crawler.start_browser()

keyword = "캠핑"
search_url = f"https://section.cafe.naver.com/ca-fe/home/search/cafes?query={keyword}"
print("Navigating to:", search_url)
crawler.driver.get(search_url)
time.sleep(5.0)

# Page source analysis or tag extraction
print("Current URL:", crawler.driver.current_url)

# Find all links containing cafe.naver.com
links = crawler.driver.find_elements(By.TAG_NAME, "a")
found = []
for idx, link in enumerate(links):
    try:
        href = link.get_attribute("href") or ""
        text = link.text or ""
        if "cafe.naver.com" in href:
            found.append((text.strip(), href.strip()))
    except Exception as e:
        pass

print(f"Found {len(found)} links:")
for f in found[:30]:
    print(" - Text:", f[0], "URL:", f[1])

crawler.close()
