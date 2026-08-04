from app.products.scraper.crawler import NaverCafeCrawler
import time
c = NaverCafeCrawler()
c.start_browser()

# 29417622 = campingfirstcar
url = "https://m.cafe.naver.com/ca-fe/cafes/29417622/members/staff"
c.driver.get(url)
time.sleep(5)

page_src = c.driver.page_source
with open('logs/my_test_mobile_staff.html', 'w', encoding='utf-8') as f:
    f.write(page_src)
print('Saved my_test_mobile_staff.html, size:', len(page_src))

c.driver.quit()
