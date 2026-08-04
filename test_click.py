from app.products.scraper.crawler import NaverCafeCrawler
c = NaverCafeCrawler()
c.start_browser()
c.driver.get('https://cafe.naver.com/CafeProfileView.nhn?clubid=14358379')
import time
time.sleep(3)
try:
    from selenium.webdriver.common.by import By
    el = c.driver.find_element(By.XPATH, "//a[contains(text(), '캠핑퍼스트매니저')]")
    print('Element found:', el.tag_name)
    el.click()
    print('Clicked!')
    time.sleep(2)
    layer = c.driver.find_element(By.ID, 'memberHtmlLayer')
    print('Layer displayed:', layer.is_displayed())
except Exception as e:
    print('Error:', e)
c.driver.quit()
