import os
import sys
import requests
import urllib.parse
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Naver Cafe Search via requests (no browser)...")
    club_id = "14358379" # campingfirst
    nickname = "캠핑퍼스트매니저"
    
    # URL encode query with euc-kr encoding
    query_encoded = urllib.parse.quote(nickname.encode('euc-kr'))
    
    # We query the PC ArticleList search endpoint directly
    url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={club_id}&search.searchBy=1&search.query={query_encoded}"
    print(f"Requesting URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://cafe.naver.com/campingfirst"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        text = res.text
        print(f"Response length: {len(text)}")
        
        # Save to file
        with open("scratch/search_requests.html", "w", encoding="utf-8") as f:
            f.write(text)
        print("Saved to scratch/search_requests.html")
        
        # Look for the nickname and onclick details
        if nickname in text:
            print(f"Found '{nickname}' in search results HTML!")
            matches = [m.start() for m in re.finditer(re.escape(nickname), text)]
            for idx, pos in enumerate(matches[:5]):
                start = max(0, pos - 250)
                end = min(len(text), pos + 250)
                print(f"\nMatch {idx + 1} at position {pos}:")
                print(text[start:end])
        else:
            print(f"Could not find '{nickname}' in the HTML response.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
