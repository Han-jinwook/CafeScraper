import os, sys, time, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.naver_login import auto_login_naver_with_js
from app.utils.paths import get_config_path

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
    
    crawler.driver.execute_cdp_cmd('Network.enable', {})
    
    crawler.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
        window.interceptedApis = [];
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);
            try {
                const cloned = response.clone();
                cloned.text().then(text => {
                    let url = typeof args[0] === 'string' ? args[0] : args[0].url;
                    window.interceptedApis.push({url: url, body: text});
                }).catch(e => {});
            } catch(e) {}
            return response;
        };
        const XHR = XMLHttpRequest.prototype;
        const open = XHR.open;
        const send = XHR.send;
        XHR.open = function(method, url) {
            this._url = url;
            return open.apply(this, arguments);
        };
        XHR.send = function() {
            this.addEventListener('load', function() {
                try {
                    window.interceptedApis.push({url: this._url, body: this.responseText});
                } catch(e) {}
            });
            return send.apply(this, arguments);
        };
        '''
    })
    
    crawler.driver.get('https://m.cafe.naver.com/logout')
    time.sleep(5.0)
    
    # Try to click the '정보' tab to trigger members API if not loaded
    try:
        from selenium.webdriver.common.by import By
        tabs = crawler.driver.find_elements(By.XPATH, "//a[contains(text(), '정보')]")
        for tab in tabs:
            crawler.driver.execute_script('arguments[0].click();', tab)
            print('Clicked a 정보 tab')
    except Exception as e:
        print('Error clicking tab:', e)
        
    time.sleep(3.0)
    
    res = crawler.driver.execute_script('return window.interceptedApis || [];')
    with open('logs/logout_apis_dump.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('Dumped APIs to logs/logout_apis_dump.json')
    crawler.close()

if __name__ == '__main__':
    main()
