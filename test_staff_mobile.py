import time
import json
from app.products.scraper.crawler import NaverCafeCrawler

c = NaverCafeCrawler()
c.start_browser()

# Log in using the crawler's method
print("Logging in...")
c.driver.get('https://nid.naver.com/nidlogin.login')
time.sleep(3)
input("Please log in manually on the browser, then press Enter here: ")

club_id = "10010818" # Logout cafe

# Inject interceptor
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

url = f"https://m.cafe.naver.com/ca-fe/cafes/{club_id}/members/staff"
print("Visiting:", url)
c.driver.get(url)
time.sleep(5)

# Dump API responses
responses = c.driver.execute_script('return window._api_responses || [];')
with open('logs/staff_mobile_responses.json', 'w', encoding='utf-8') as f:
    json.dump(responses, f, ensure_ascii=False, indent=2)
print("Dumped logs/staff_mobile_responses.json")

c.driver.quit()
