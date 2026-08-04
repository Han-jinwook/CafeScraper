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
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    auto_login_naver_with_js(crawler, cfg.get('marketer_naver_id', '').strip(), cfg.get('marketer_naver_pw', ''))
    time.sleep(2)
    
    crawler.driver.get('https://cafe.naver.com/logout')
    time.sleep(2)
    
    cookies = crawler.driver.get_cookies()
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
    res = session.get('https://cafe.naver.com/CafeMemberViewList.nhn?search.clubid=10010818&search.query=아라&search.searchBy=1')
    with open('logs/member_search.html', 'w', encoding='utf-8') as f:
        f.write(res.text)
        
    print('Saved to logs/member_search.html')
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, 'html.parser')
    for a in soup.find_all('a', class_='m-tcol-c'):
        print('Found member link:', a.text.strip(), 'onclick:', a.get('onclick', ''))
        
    crawler.close()

if __name__ == '__main__':
    main()
