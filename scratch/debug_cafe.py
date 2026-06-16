import json
import os
import sys
import time
from datetime import datetime
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

def main():
    # Load config
    config_path = "user_settings.json"
    if not os.path.exists(config_path):
        config_path = "crawler_config.json"
    if not os.path.exists(config_path):
        print("Config not found")
        return
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    chrome_profile = os.path.join(os.getcwd(), "sessions", "event")
        
    print(f"Using profile: {chrome_profile}")
    
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={chrome_profile}")
    options.add_argument("--profile-directory=Default")
    
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"Failed to launch Chrome: {e}")
        return
            
    try:
        # Go to cafe main or board list
        target_url = "https://cafe.naver.com/ArticleList.nhn?search.clubid=12412554&search.boardtype=L"
        print(f"Navigating to: {target_url}")
        driver.get(target_url)
        time.sleep(5)
        
        # Print page source info
        print(f"Current URL: {driver.current_url}")
        
        # Check if we need to switch to iframe
        if "cafe.naver.com" in driver.current_url:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"Iframes on page: {[iframe.get_attribute('id') or iframe.get_attribute('name') for iframe in iframes]}")
            
            try:
                driver.switch_to.frame("cafe_main")
                print("Switched to cafe_main frame successfully")
            except Exception as fe:
                print(f"Could not switch to cafe_main: {fe}")
                
        # Find rows
        row_selector = "tr[class*='article'], div.article-board table tbody tr, table tbody tr"
        rows = driver.find_elements(By.CSS_SELECTOR, row_selector)
        print(f"Found {len(rows)} rows")
        
        for idx, row in enumerate(rows[:15]):
            print(f"--- Row {idx+1} ---")
            print(f"Text: {row.text.replace(chr(10), ' ')}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
