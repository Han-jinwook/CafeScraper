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
    print("Testing Naver Cafe Member Profile API interception via CDP network logs...")
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
        print(f"🔑 로그인 시도 중 (ID: {login_id})...")
        success, reason = auto_login_naver_with_js(crawler, login_id, login_pw)
        print(f"🔑 로그인 상태: {success}")
        time.sleep(2)
        
        # Navigate to profile URL
        club_id = "14358379"
        member_key = "Ta4qKK0NoroVi-J5TrgF68zv7dzzefVlrfBfK1CZBA0"
        url = f"https://cafe.naver.com/CafeMemberNetworkView.nhn?m=view&clubid={club_id}&memberid={member_key}"
        print(f"Navigating to profile: {url}")
        
        # Inject hook to window.fetch and window.history
        # This will intercept both traditional fetch/XHR and client-side history state updates
        hook_js = """
        (function() {
            window.intercepted_requests = [];
            var origOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url) {
                window.intercepted_requests.push({ type: 'xhr', url: url });
                return origOpen.apply(this, arguments);
            };
            var origFetch = window.fetch;
            window.fetch = function(input, init) {
                var url = typeof input === 'string' ? input : (input && input.url) ? input.url : '';
                if (url) window.intercepted_requests.push({ type: 'fetch', url: url });
                return origFetch.apply(this, arguments);
            };
        })();
        """
        crawler.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": hook_js
        })
        
        crawler.driver.get(url)
        time.sleep(6.0) # Wait enough for Next.js to call backends
        
        # Fetch intercepted logs
        logs = crawler.driver.execute_script("return window.intercepted_requests || [];")
        print("\n--- Intercepted Network Requests ---")
        for log in logs:
            print(f"Type: {log['type']}, URL: {log['url']}")
        print("------------------------------------\n")
        
        # Also print page source after rendering completes (since loading spinner is visible at first)
        rendered_html = crawler.driver.page_source
        with open("scratch/jsp_profile_rendered.html", "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print(f"Saved rendered profile HTML to scratch/jsp_profile_rendered.html (length: {len(rendered_html)})")
        
        # Search for blogId or naver links
        import re
        blog_matches = re.findall(r"blog\.naver\.com/([a-zA-Z0-9_-]+)", rendered_html)
        print(f"Rendered HTML blog matches: {blog_matches}")
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
