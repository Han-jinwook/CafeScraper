import os
import sys
import requests
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("Testing Naver Cafe Intro API response...")
    club_id = "14358379" # campingfirst clubid
    url = f"https://apis.naver.com/cafe-web/cafe2/CafeIntroInfo.json?clubid={club_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://cafe.naver.com/CafeIntro.nhn?clubid={club_id}"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        print("Raw Response:")
        print(res.text[:3000])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
