
import os, sys, time, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.products.scraper.crawler import NaverCafeCrawler
c = NaverCafeCrawler(debug_mode=True)
c.start_browser()
c.driver.get('https://cafe.naver.com/CafeProfileView.nhn?clubid=10010818')
time.sleep(3)
from selenium.webdriver.common.by import By
links = c.driver.find_elements(By.CSS_SELECTOR, 'td.p-nick a')
if links:
    print('Found link, clicking...')
    c.driver.execute_script('arguments[0].click();', links[0])
    time.sleep(2)
    layers = c.driver.find_elements(By.CLASS_NAME, 'perid-layer')
    if layers and layers[0].is_displayed():
        print('Layer appeared! HTML:', layers[0].get_attribute('outerHTML'))
    else:
        print('No layer appeared!')
else:
    print('Link not found')
c.driver.quit()
