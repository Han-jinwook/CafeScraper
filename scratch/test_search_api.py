import time
import requests
import json

# Let's search using Naver Cafe's search API or search page's API.
# Query: 캠핑
# Let's try requests to see if there is an API or we can parse section search page.
# Under section.cafe.naver.com, let's see how search results are populated.
# It uses: https://section.cafe.naver.com/api/search/cafes?query=캠핑&pageNo=1&sortBy=0

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://section.cafe.naver.com/ca-fe/home/search/cafes?query=%EC%BA%A0%ED%95%91"
}

url = "https://section.cafe.naver.com/api/search/cafes?query=%EC%BA%A0%ED%95%91&pageNo=1&sortBy=0"
print("Requesting URL:", url)
res = requests.get(url, headers=headers)
print("Status code:", res.status_code)
try:
    data = res.json()
    print("Response JSON structure:")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    
    cafes = data.get("message", {}).get("result", {}).get("searchCafeList", [])
    print(f"Found {len(cafes)} cafes in searchCafeList:")
    for c in cafes[:10]:
        print(f" - Cafe Name: {c.get('cafeName')} | Cafe URL: https://cafe.naver.com/{c.get('cafeUrl')} | Members: {c.get('memberCount')}")
except Exception as e:
    print("Error parsing JSON:", e)
    print("Response text snippet:", res.text[:500])
