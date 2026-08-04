import os
import sys
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing PC Search (special_tab&tab=cafe) via requests...")
    query = "캠핑"
    encoded = urllib.parse.quote(query)
    url = f"https://search.naver.com/search.naver?where=special_tab&query={encoded}&tab=cafe"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a")
            cafe_ids = set()
            print(f"Total links found: {len(links)}")
            for idx, link in enumerate(links):
                href = link.get("href", "")
                text = link.text or ""
                if "cafe.naver.com" in href:
                    match = re.search(r"cafe\.naver\.com/([a-zA-Z0-9_]+)", href)
                    if match:
                        cid = match.group(1)
                        if cid not in ("ca-fe", "ArticleRead", "ArticleList", "MyCafeIntro"):
                            cafe_ids.add(cid)
                            print(f" - Found Cafe ID: {cid} (Text: {text.strip()}, Link: {href})")
            
            print(f"\nFinal collected Cafe IDs ({len(cafe_ids)}): {list(cafe_ids)}")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    main()
