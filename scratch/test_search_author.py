import os
import sys
import time
import urllib.parse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing Naver Cafe Search by Author Fallback...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        
        # 🔑 저장된 네이버 계정 정보 로드
        from app.utils.paths import get_config_path
        import json
        config_path = get_config_path()
        login_id, login_pw = "", ""
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                login_id = cfg.get("marketer_naver_id", "").strip()
                login_pw = cfg.get("marketer_naver_pw", "")
        
        # 🔑 자동 로그인 시도
        from app.utils.naver_login import auto_login_naver_with_js
        print(f"🔑 자동 로그인 시도 중 (ID: {login_id})...")
        success, reason = auto_login_naver_with_js(crawler, login_id, login_pw)
        print(f"🔑 로그인 상태: {success} ({reason})")
        time.sleep(2)
        
        # Navigate to cafe main page first
        cafe_url = "https://cafe.naver.com/campingfirst"
        print(f"Navigating to Cafe URL: {cafe_url}")
        crawler.driver.get(cafe_url)
        time.sleep(4.0)
        
        # Navigate the iframe internally using JavaScript
        club_id = "14358379"
        nickname = "캠핑퍼스트매니저"
        # We euc-kr encode the query parameter for Naver Cafe compatibility
        query_encoded = urllib.parse.quote(nickname.encode('euc-kr'))
        
        iframe_src = f"/ArticleSearchList.nhn?search.clubid={club_id}&search.searchBy=1&search.query={query_encoded}"
        print(f"Navigating iframe to: {iframe_src}")
        
        # We run this from the default top-level context
        crawler.driver.switch_to.default_content()
        nav_js = f"""
        (function() {{
            var iframe = document.getElementById('cafe_main');
            if (iframe) {{
                iframe.src = '{iframe_src}';
                return "OK";
            }}
            return "IFRAME_NOT_FOUND";
        }})()
        """
        nav_res = crawler._execute_js_via_cdp(nav_js)
        print(f"Iframe Navigation Result: {nav_res}")
        time.sleep(4.0)
        
        # Switch to cafe_main iframe
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if switched:
            print("Switched to cafe_main iframe.")
            
            # Extract page source via CDP
            get_html_js = """
            (function() {
                var iframe = document.getElementById('cafe_main');
                var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
                return doc.documentElement.outerHTML;
            })()
            """
            inner_html = crawler._execute_js_via_cdp(get_html_js)
            
            output_file = "scratch/search_result_iframe.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(inner_html)
            print(f"Saved search result iframe HTML to {output_file} (length: {len(inner_html)})")
            
            # Let's search for "캠핑퍼스트매니저" and look for onclick attributes or memberid
            if nickname in inner_html:
                print(f"Found '{nickname}' in search results!")
                # Find all occurrences of the nickname and print their surrounding HTML
                import re
                matches = [m.start() for m in re.finditer(re.escape(nickname), inner_html)]
                for idx, pos in enumerate(matches[:5]):
                    start = max(0, pos - 250)
                    end = min(len(inner_html), pos + 250)
                    print(f"\nMatch {idx + 1} at position {pos}:")
                    print(inner_html[start:end])
            else:
                print(f"Could not find '{nickname}' in the search results.")
        else:
            print("Failed to switch to cafe_main iframe.")
            
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
