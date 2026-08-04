import os
import sys
import requests
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Naver Cafe Intro Info API...")
    club_id = "14358379" # campingfirst clubid
    
    # We test both pc apis.naver.com and m.cafe.naver.com endpoints
    endpoints = [
        f"https://apis.naver.com/cafe-web/cafe2/CafeIntroInfo.json?clubid={club_id}",
        f"https://apis.naver.com/cafe-web/cafe-intro-info?clubid={club_id}",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://cafe.naver.com/CafeIntro.nhn?clubid={club_id}"
    }
    
    for url in endpoints:
        print(f"\nRequesting: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print("Successfully loaded JSON!")
                # Dump a preview of keys
                print("JSON keys:", list(data.keys()))
                
                # Check for manager and staff info
                cafe_intro = data.get("message", {}).get("result", {}).get("cafeIntro", {})
                if not cafe_intro:
                    cafe_intro = data.get("result", {}).get("cafeIntro", {})
                if not cafe_intro:
                    cafe_intro = data
                
                # Print a formatted preview of cafeIntro or result
                print(json.dumps(cafe_intro, indent=2, ensure_ascii=False)[:1200])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
