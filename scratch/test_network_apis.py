import sys
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

options = Options()
options.add_argument('--headless')
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
driver = webdriver.Chrome(options=options)

print("Navigating to mobile info page...")
driver.get("https://m.cafe.naver.com/campingfirst/info")
time.sleep(5)

logs = driver.get_log("performance")
apis = []

for entry in logs:
    log = json.loads(entry["message"])["message"]
    if log["method"] == "Network.requestWillBeSent":
        url = log["params"]["request"]["url"]
        if "apis.naver.com" in url or "bff.cafe.naver.com" in url:
            apis.append(url)

print("Found APIs:")
for u in set(apis):
    print(u)

driver.quit()
