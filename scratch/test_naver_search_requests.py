import requests
from bs4 import BeautifulSoup
import urllib.parse

keyword = "캠핑"
encoded_keyword = urllib.parse.quote(keyword)
url = f"https://search.naver.com/search.naver?where=cafe&query={encoded_keyword}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("Fetching URL:", url)
res = requests.get(url, headers=headers)
print("Status code:", res.status_code)

soup = BeautifulSoup(res.text, "html.parser")

# Naver Cafe search results on naver.com typically have links to cafe.naver.com/{cafe_id}
# Let's find all 'a' tags with class containing 'cafe' or check all links to cafe.naver.com
found = []
links = soup.find_all("a")
for link in links:
    href = link.get("href", "")
    text = link.get_text().strip()
    if "cafe.naver.com" in href:
        found.append((text, href))

print(f"Found {len(found)} links:")
for idx, f in enumerate(found[:30]):
    print(f"[{idx}] Text: {f[0]} | URL: {f[1]}")
