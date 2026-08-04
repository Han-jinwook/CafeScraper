import os
import sys
import requests
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Mobile Cafe Article List via requests...")
    club_id = "14358379"
    url = f"https://m.cafe.naver.com/ArticleList.nhn?search.clubid={club_id}"
    print(f"Requesting mobile URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        text = res.text
        print(f"Response length: {len(text)}")
        
        with open("scratch/mobile_list.html", "w", encoding="utf-8") as f:
            f.write(text)
        print("Saved to scratch/mobile_list.html")
        
        # Look for "memberId" or "writer" or "blogId" or "userId"
        for kw in ["memberId", "writer", "blogId", "userId", "naver.com", "writerId"]:
            if kw in text:
                print(f"Found keyword '{kw}' in mobile list HTML!")
                matches = [m.start() for m in re.finditer(re.escape(kw), text)]
                for idx, pos in enumerate(matches[:3]):
                    start = max(0, pos - 150)
                    end = min(len(text), pos + 150)
                    print(f"  Match {idx+1}: {text[start:end]}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
