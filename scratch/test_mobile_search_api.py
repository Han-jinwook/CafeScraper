import os
import sys
import requests
import urllib.parse
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Mobile Cafe Article Search API...")
    club_id = "14358379"
    nickname = "두부"
    
    # URL encode with utf-8
    query_encoded = urllib.parse.quote(nickname)
    
    url = f"https://apis.naver.com/cafe-web/cafe-mobile/CafeArticleSearchList?cafeId={club_id}&query={query_encoded}&searchBy=1&sortBy=date&page=1"
    print(f"Requesting: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Referer": f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/search/articles?q={query_encoded}"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        data = res.json()
        
        # Save to file
        with open("scratch/search_api_res.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved to scratch/search_api_res.json")
        
        # Check if the author details exist
        result = data.get("result", {})
        article_list = result.get("articleList", [])
        print(f"Found {len(article_list)} articles in search results.")
        
        if article_list:
            first = article_list[0]
            print("\nFirst article keys:", first.keys())
            print("Article title:", first.get("subject"))
            print("Writer nickname:", first.get("writerNickname"))
            print("Writer ID (real Naver ID):", first.get("writerId"))
            print("Writer memberKey:", first.get("memberKey"))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
