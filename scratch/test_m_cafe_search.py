import os
import sys
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Mobile Search (m_cafe) via requests...")
    query = "캠핑"
    encoded = urllib.parse.quote(query)
    url = f"https://m.search.naver.com/search.naver?where=m_cafe&query={encoded}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a")
            cafe_ids = set()
            print(f"Total links found in HTML: {len(links)}")
            for idx, link in enumerate(links):
                href = link.get("href", "")
                text = link.text or ""
                # We look for cafe.naver.com in link
                if "cafe.naver.com" in href:
                    match = re.search(r"cafe\.naver\.com/([a-zA-Z0-9_]+)", href)
                    if match:
                        cid = match.group(1)
                        if cid not in ("ca-fe", "ArticleRead", "ArticleList", "MyCafeIntro", "m"):
                            cafe_ids.add(cid)
                            print(f" - Found Cafe ID: {cid} (Text: {text.strip()}, Link: {href})")
            
            print(f"\nFinal collected Cafe IDs ({len(cafe_ids)}): {list(cafe_ids)}")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    main()
