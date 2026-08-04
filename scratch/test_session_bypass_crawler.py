import os
import time
import sys

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Enable environment bypass variable
os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing NaverCafeCrawler with Session 0 Bypass...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    def status_cb(msg):
        print(f"[STATUS] {msg}")
    crawler.set_status_callback(status_cb)
    
    try:
        crawler.start_browser()
        print("Browser started successfully!")
        print(f"Driver URL: {crawler.driver.current_url}")
        time.sleep(5)
        crawler.close()
        print("Crawler closed successfully. Test PASS!")
    except Exception as e:
        import traceback
        print(f"Test FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
