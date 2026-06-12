import json
import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

def main():
    chrome_profile = os.path.join(os.getcwd(), "sessions", "event")
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={chrome_profile}")
    options.add_argument("--profile-directory=Default")
    
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"Failed to launch Chrome: {e}")
        return
            
    try:
        target_url = "https://cafe.naver.com/f-e/cafes/12412554/menus/0?viewType=L"
        driver.get(target_url)
        time.sleep(5)
        
        # Find rows
        row_selector = "tr[class*='article'], div.article-board table tbody tr, table tbody tr"
        rows = driver.find_elements(By.CSS_SELECTOR, row_selector)
        print(f"Found {len(rows)} rows")
        
        for idx, row in enumerate(rows):
            cls = row.get_attribute("class")
            text = row.text.replace('\n', ' ')
            print(f"Row {idx+1}: Class='{cls}', Text='{text}'")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
