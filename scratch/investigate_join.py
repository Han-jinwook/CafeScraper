import os, sys, time, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.naver_login import auto_login_naver_with_js
from app.utils.paths import get_config_path
from bs4 import BeautifulSoup
import re

def main():
    crawler = NaverCafeCrawler(debug_mode=True)
    crawler.start_browser()
    config_path = get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    auto_login_naver_with_js(crawler, cfg.get('marketer_naver_id', ''), cfg.get('marketer_naver_pw', ''))
    time.sleep(2)
    
    # campingfirst
    crawler.driver.get('https://cafe.naver.com/CafeMemberJoinSetup.nhn?clubid=14358379')
    time.sleep(3)
    
    html = crawler.driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Nickname rules
    nick_rule = soup.find('p', class_='nick_rule')
    print("Nickname Rule:", nick_rule.text.strip() if nick_rule else "None")
    
    # 2. Join questions
    questions = soup.find_all('div', class_='question_area')
    for q in questions:
        q_text = q.find('strong', class_='q_text')
        print("Question:", q_text.text.strip() if q_text else "None")
    
    # 3. Check for Captcha
    captcha = soup.find(id='captcha')
    print("Captcha exists:", bool(captcha))
    
    crawler.close()

if __name__ == '__main__':
    main()
