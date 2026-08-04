import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing Chrome CDP Runtime.evaluate bypass...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        
        # Test 1: Simple evaluation
        js_simple = "document.title"
        res_simple = crawler.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": js_simple,
            "returnByValue": True
        })
        print(f"CDP Simple Result: {res_simple}")
        val = res_simple.get("result", {}).get("value")
        print(f"Title value obtained: {val}")
        
        # Test 2: Complex script execution (IIFE)
        js_complex = """
        (function() {
            var ths = document.querySelectorAll('th');
            return "Found ths count: " + ths.length;
        })()
        """
        res_complex = crawler.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": js_complex,
            "returnByValue": True
        })
        print(f"CDP Complex Result: {res_complex}")
        val_complex = res_complex.get("result", {}).get("value")
        print(f"Complex value obtained: {val_complex}")
        
        crawler.close()
        print("CDP test finished. PASS!")
    except Exception as e:
        print(f"CDP test FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
