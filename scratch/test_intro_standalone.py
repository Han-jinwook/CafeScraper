import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing Naver Cafe Intro page standalone...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        club_id = "14358379" # campingfirst
        intro_url = f"https://cafe.naver.com/CafeIntro.nhn?clubid={club_id}"
        print(f"Navigating directly to: {intro_url}")
        crawler.driver.get(intro_url)
        time.sleep(5.0)
        
        # Save page source
        page_src = crawler.driver.page_source
        output_file = "scratch/intro_standalone_source.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(page_src)
        print(f"Saved standalone source to {output_file} (length: {len(page_src)})")
        
        # Search for campingfirst manager name
        if "캠핑퍼스트매니저" in page_src:
            print("Found '캠핑퍼스트매니저' in standalone HTML!")
            idx = page_src.index("캠핑퍼스트매니저")
            start = max(0, idx - 800)
            end = min(len(page_src), idx + 800)
            print("--- Snippet around manager ---")
            print(page_src[start:end])
            print("------------------------------")
            
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
