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
    print("Testing Member Key to Naver ID Resolution...")
    club_id = "14358379"
    member_key = "Ta4qKK0NoroVi-J5TrgF68zv7dzzefVlrfBfK1CZBA0"
    
    url = f"https://cafe.naver.com/f-e/cafes/{club_id}/members/{member_key}"
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
        with open("scratch/member_profile.html", "w", encoding="utf-8") as f:
            f.write(text)
        print("Saved to scratch/member_profile.html")
        
        # Let's search for Naver IDs or blog IDs
        # Usually Naver IDs are alphanumeric and 3-20 chars. Let's look for "blogId" or "blog.naver.com"
        for keyword in ["blogId", "blogid", "blog.naver.com", "naver.com", "userId", "userid", "memberId", "memberid"]:
            if keyword in text.lower():
                print(f"Found keyword '{keyword}' in profile HTML!")
                # Print around it
                matches = [m.start() for m in re.finditer(re.escape(keyword), text, re.I)]
                for idx, pos in enumerate(matches[:5]):
                    start = max(0, pos - 150)
                    end = min(len(text), pos + 150)
                    print(f"  Match {idx + 1}:")
                    print(text[start:end])
            else:
                print(f"Keyword '{keyword}' not found.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
