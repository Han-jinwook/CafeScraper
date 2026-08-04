import os
import sys
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing Naver Cafe Search API via Interactive Browser...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        
        # 1. API URL로 브라우저 이동
        api_url = "https://m.cafe.naver.com/api/cafe/search?query=%EC%BA%A0%ED%95%91&page=1&size=20"
        print(f"Navigating to API: {api_url}")
        crawler.driver.get(api_url)
        time.sleep(3.0)
        
        # 2. JSON 결과 텍스트 추출
        # 브라우저가 JSON을 렌더링하면 <pre> 태그에 들어가거나 그냥 body text로 들어감
        raw_text = crawler.driver.execute_script("return document.body.innerText;")
        print(f"Raw Text Preview (first 200 chars): {raw_text[:200]}")
        
        data = json.loads(raw_text)
        cafes = data.get("message", {}).get("result", {}).get("cafeList", [])
        
        print(f"Found {len(cafes)} cafes via API:")
        for idx, cafe in enumerate(cafes):
            name = cafe.get("cafeName")
            cafe_url = cafe.get("cafeUrl")
            member_count = cafe.get("memberCount")
            print(f" [{idx+1}] {name} ({cafe_url}) - 회원수: {member_count}")
            
        crawler.close()
        print("API test finished. PASS!")
    except Exception as e:
        print(f"API test FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
