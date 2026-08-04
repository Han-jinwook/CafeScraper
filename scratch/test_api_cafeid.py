import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Naver Cafe APIs with cafeId...")
    cafe_id = "14358379"
    
    urls = [
        f"https://apis.naver.com/cafe-web/cafe2/CafeIntro.json?cafeId={cafe_id}",
        f"https://apis.naver.com/cafe-web/cafe2/CafeIntroInfo.json?cafeId={cafe_id}",
        f"https://apis.naver.com/cafe-web/cafe-mobile/CafeIntro.json?cafeId={cafe_id}",
        f"https://apis.naver.com/cafe-web/cafe-mobile/CafeIntroInfo.json?cafeId={cafe_id}",
        f"https://apis.naver.com/cafe-web/cafe2/CafeIntro.json?clubid={cafe_id}",
        f"https://apis.naver.com/cafe-web/cafe-mobile/CafeIntro.json?clubid={cafe_id}",
        f"https://apis.naver.com/cafe-home-web/cafe-home/v1/member/identifier?cafeId={cafe_id}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://cafe.naver.com/campingfirst"
    }
    
    for url in urls:
        print(f"\nRequesting: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=5)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                print(f"Content (first 500 chars): {res.text[:500]}")
                if "manager" in res.text or "staff" in res.text or "member" in res.text:
                    print("--> Found interesting keywords!")
            else:
                print(f"Response: {res.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
