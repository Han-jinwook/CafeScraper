from app.products.scraper.crawler import NaverCafeCrawler
import time
import json

c = NaverCafeCrawler()
c.start_browser()

inject_js = """
window._api_responses = [];
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    try {
        const cloned = response.clone();
        cloned.text().then(text => {
            let url = args[0];
            if (url && typeof url === 'object' && url.url) {
                url = url.url;
            }
            window._api_responses.push({
                url: url,
                body: text
            });
        }).catch(e => {});
    } catch(e) {}
    return response;
};
"""
c.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': inject_js})

c.driver.get('https://m.cafe.naver.com/ca-fe/web/cafes/29417622/members?tab=staff')
time.sleep(6)

responses = c.driver.execute_script('return window._api_responses;')
found = False
for r in responses:
    url = r.get('url', '')
    print('URL:', url)
    print('BODY:', r.get('body', '')[:200])
    found = True

if not found:
    print("No matching APIs found in interceptor!")

c.driver.quit()
