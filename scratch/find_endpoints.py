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
    url = "https://ca-fe.pstatic.net/web-section/js/Introduction.da79d423.js"
    print(f"Downloading JavaScript bundle: {url}")
    
    try:
        res = requests.get(url, timeout=10)
        print(f"Status: {res.status_code}")
        text = res.text
        print(f"JS Length: {len(text)}")
        
        # Save to file
        with open("scratch/Introduction.js", "w", encoding="utf-8") as f:
            f.write(text)
            
        # Search for apis.naver.com or /v1/ or /v2/ or GraphQL queries or URLs
        # Matches any URLs or API-like paths
        paths = re.findall(r"['\"]([^'\"]*?/cafe-web/.*?|.*?/graphql.*?)['\"]", text)
        print(f"Found paths (cafe-web / graphql): {set(paths)}")
        
        # Let's search for keywords like "clubId", "cafeId", "manager", "staff"
        for kw in ["manager", "staff", "introduction", "intro", "CafeIntro", "GateInfo", "CafeGateInfo"]:
            matches = [m.start() for m in re.finditer(re.escape(kw), text, re.I)]
            print(f"Keyword '{kw}' matches count: {len(matches)}")
            for pos in matches[:3]:
                start = max(0, pos - 100)
                end = min(len(text), pos + 100)
                print(f"  Snippet: {text[start:end]}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
