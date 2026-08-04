import os, sys, time, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.naver_login import auto_login_naver_with_js
from app.utils.paths import get_config_path
import requests

def main():
    crawler = NaverCafeCrawler(debug_mode=True)
    crawler.start_browser()
    config_path = get_config_path()
    login_id, login_pw = '', ''
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            login_id = cfg.get('marketer_naver_id', '').strip()
            login_pw = cfg.get('marketer_naver_pw', '')
            
    auto_login_naver_with_js(crawler, login_id, login_pw)
    time.sleep(2)
    
    crawler.driver.get('https://m.cafe.naver.com/')
    time.sleep(2)
    
    cookies = crawler.driver.get_cookies()
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
    res = session.get('https://apis.naver.com/cafe-web/cafe-cafeinfo-api/v1.0/cafes/10010818/members', 
                      headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    print('Status:', res.status_code)
    print('Headers:', dict(res.headers))
    print('Text:', res.text[:500])
    
    with open('logs/staff_api_requests.json', 'w', encoding='utf-8') as f:
        f.write(res.text)
        
    print('Saved to logs/staff_api_requests.json')
    crawler.close()

if __name__ == '__main__':
    main()
