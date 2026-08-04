import sys
import os
import re
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def test_api():
    chrome_options = Options()
    chrome_options.debugger_address = "127.0.0.1:9222"
    driver = webdriver.Chrome(options=chrome_options)
    
    # Get club id for campingfirst
    club_id = "14358379" # campingfirst
    nickname = "캠핑퍼스트매니저"
    
    # Copy cookies
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Referer": "https://cafe.naver.com/"
    }
    
    # Test CafeArticleSearchList
    import urllib.parse
    encoded_nick = urllib.parse.quote(nickname)
    url = f"https://apis.naver.com/cafe-web/cafe-mobile/CafeArticleSearchList?cafeId={club_id}&query={encoded_nick}&searchBy=1&sortBy=date&page=1"
    
    print(f"Requesting URL: {url}")
    res = session.get(url, headers=headers, timeout=10)
    print(f"Status Code: {res.status_code}")
    try:
        data = res.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Response text: {res.text[:1000]}")

if __name__ == "__main__":
    test_api()
