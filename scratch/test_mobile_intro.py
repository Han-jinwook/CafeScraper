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
    print("Testing Naver Cafe Mobile Intro Page...")
    club_id = "14358379" # campingfirst
    
    # We test both direct cafe name and CafeIntro endpoints
    urls = [
        f"https://m.cafe.naver.com/CafeIntro.nhn?clubid={club_id}",
        f"https://m.cafe.naver.com/campingfirst"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://m.naver.com"
    }
    
    for url in urls:
        print(f"\nFetching: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {res.status_code}")
            text = res.text
            print(f"Response length: {len(text)}")
            
            # Save it to a file
            filename = f"scratch/mobile_intro_{'club' if 'clubid' in url else 'name'}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Saved to {filename}")
            
            # Let's search for "캠핑퍼스트매니저" or "두부"
            nickname = "캠핑퍼스트매니저"
            if nickname in text:
                print(f"Found '{nickname}' in source!")
                idx = text.index(nickname)
                start = max(0, idx - 400)
                end = min(len(text), idx + 400)
                print("--- Snippet ---")
                print(text[start:end])
                print("---------------")
            else:
                print(f"Could not find '{nickname}' in source.")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
