import os, sys, time, json, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.naver_login import auto_login_naver_with_js
from app.utils.paths import get_config_path
from bs4 import BeautifulSoup

def find_contacts(text):
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    phones = re.findall(r'010[-.\s]?\d{3,4}[-.\s]?\d{4}|\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}', text)
    kakao_links = re.findall(r'https?://(?:open|pf)\.kakao\.com/[a-zA-Z0-9_/-]+', text)
    kakao_ids = re.findall(r'카톡\s*아이디\s*[:=]?\s*([a-zA-Z0-9_]+)|카카오톡\s*ID\s*[:=]?\s*([a-zA-Z0-9_]+)', text)
    
    # Clean up phone numbers to avoid false positives with just numbers
    valid_phones = []
    for p in phones:
        if len(re.sub(r'[^0-9]', '', p)) >= 9:
            valid_phones.append(p)
            
    # Flatten kakao ids
    k_ids = [item for sublist in kakao_ids for item in sublist if item]
            
    return {
        'emails': list(set(emails)),
        'phones': list(set(valid_phones)),
        'kakao_links': list(set(kakao_links)),
        'kakao_ids': list(set(k_ids))
    }

def analyze_cafe(crawler, club_name):
    print(f"\n--- Analyzing Cafe: {club_name} ---")
    crawler.driver.get(f"https://cafe.naver.com/{club_name}")
    time.sleep(3)
    
    try:
        html = crawler.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Get Club ID
        m = re.search(r'clubid=(\d+)', html)
        clubid = m.group(1) if m else None
        print(f"Club ID: {clubid}")
        
        # Search Main Page HTML
        main_contacts = find_contacts(soup.get_text())
        main_html_contacts = find_contacts(html)
        
        print("Contacts found on Main Page:")
        print(f"Emails: {main_html_contacts['emails']}")
        print(f"Phones: {main_html_contacts['phones']}")
        print(f"Kakao Links: {main_html_contacts['kakao_links']}")
        
        if not clubid:
            return
            
        # 2. Get Cafe Profile/Intro
        crawler.driver.get(f"https://cafe.naver.com/CafeProfileView.nhn?clubid={clubid}")
        time.sleep(2)
        intro_html = crawler.driver.page_source
        intro_soup = BeautifulSoup(intro_html, 'html.parser')
        intro_contacts = find_contacts(intro_soup.get_text())
        
        print("Contacts found in Profile/Intro:")
        print(f"Emails: {intro_contacts['emails']}")
        print(f"Phones: {intro_contacts['phones']}")
        print(f"Kakao Links: {intro_contacts['kakao_links']}")
        
        # 3. Get Cafe Gate (대문) if it exists
        crawler.driver.get(f"https://cafe.naver.com/CafeGateInfo.nhn?clubid={clubid}")
        time.sleep(2)
        gate_html = crawler.driver.page_source
        gate_soup = BeautifulSoup(gate_html, 'html.parser')
        gate_contacts = find_contacts(gate_html)
        
        print("Contacts found in Gate (대문 HTML):")
        print(f"Emails: {gate_contacts['emails']}")
        print(f"Phones: {gate_contacts['phones']}")
        print(f"Kakao Links: {gate_contacts['kakao_links']}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")

def main():
    crawler = NaverCafeCrawler(debug_mode=True)
    crawler.start_browser()
    config_path = get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    auto_login_naver_with_js(crawler, cfg.get('marketer_naver_id', ''), cfg.get('marketer_naver_pw', ''))
    time.sleep(2)
    
    test_cafes = [
        "campingfirst",        # Big camping cafe
        "campingfirstcar",     # Another camping cafe
        "joonggonara",         # Junggonara (huge cafe, lots of business info)
        "dieselmania"          # Dieselmania
    ]
    
    for cafe in test_cafes:
        analyze_cafe(crawler, cafe)
        
    crawler.close()

if __name__ == '__main__':
    main()
