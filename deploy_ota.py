import os
import sys
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

SUPABASE_URL = "https://suwinftalfgybvrnzruz.supabase.co"

def upload_zip(zip_filepath, github_pat, upload_url, headers):
    zip_filename = os.path.basename(zip_filepath)
    if not os.path.exists(zip_filepath):
        print(f"[ERROR] ZIP file not found: {zip_filepath}")
        return False

    print(f"Uploading {zip_filename} to GitHub Release...")
    upload_headers = headers.copy()
    upload_headers["Content-Type"] = "application/zip"
    
    import time
    for attempt in range(3):
        try:
            with open(zip_filepath, "rb") as f:
                res_upload = requests.post(f"{upload_url}?name={zip_filename}", data=f, headers=upload_headers, timeout=180.0)
                res_upload.raise_for_status()
            print(f"Upload complete for {zip_filename}")
            return True
        except Exception as e:
            print(f"Upload attempt {attempt+1} failed: {e}")
            time.sleep(3)
    return False

def main():
    # Load version from version.txt
    with open("version.txt", "r", encoding="utf-8") as f:
        version = f.read().strip()
    
    print(f"[OTA Deployer] Starting DUAL OTA Deployment for CafeScraper v{version}...")
    
    load_dotenv()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    github_pat = os.getenv("GITHUB_PAT")
    
    if not service_key or not github_pat:
        print("[ERROR] Missing required keys in .env file.")
        sys.exit(1)
        
    print("Keys loaded successfully.")
    
    github_repo = "Han-jinwook/CafeScraper"
    tag_name = f"v{version}"
    print(f"Creating GitHub Release {tag_name} in {github_repo}...")
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_pat}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    release_payload = {
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": f"Release {tag_name}",
        "body": f"Auto-generated release for CafeScraper v{version}",
        "draft": False,
        "prerelease": False,
        "generate_release_notes": False
    }
    
    res = requests.post(f"https://api.github.com/repos/{github_repo}/releases", json=release_payload, headers=headers)
    if res.status_code == 201:
        release_data = res.json()
        upload_url = release_data["upload_url"].split("{")[0]
        print("GitHub Release created successfully.")
    elif res.status_code == 422: # Already exists
        print("Release tag already exists. Fetching existing release...")
        res_get = requests.get(f"https://api.github.com/repos/{github_repo}/releases/tags/{tag_name}", headers=headers)
        res_get.raise_for_status()
        release_data = res_get.json()
        upload_url = release_data["upload_url"].split("{")[0]
        
        # Clean up existing assets
        for asset in release_data.get("assets", []):
            print(f"Deleting existing asset {asset['name']}...")
            requests.delete(asset["url"], headers=headers)
    else:
        print(f"[ERROR] Failed to create GitHub Release: {res.status_code} - {res.text}")
        sys.exit(1)
        
    # Upload the 4 ZIP files from dist directory
    zip_files = [
        "CafeCrawler-Pro.zip",
        "EventStats-Pro.zip",
        "AutoComment-Pro.zip",
        "CafeMonster-Trial.zip"
    ]
    
    for z in zip_files:
        zip_path = os.path.join("dist", z)
        success = upload_zip(zip_path, github_pat, upload_url, headers)
        if not success:
            print(f"[WARNING] Failed to upload {z}")
            
    # Supabase - Update app_versions Table for all 3 products
    print("Registering version in Supabase app_versions table...")
    supabase: Client = create_client(SUPABASE_URL, service_key)
    
    products = [
        {"id": "CafeCrawler", "name": "카페 수집기 Pro", "zip": "CafeCrawler-Pro.zip"},
        {"id": "EventStats", "name": "이벤트 활동 분석기", "zip": "EventStats-Pro.zip"},
        {"id": "AutoComment", "name": "자동댓글러", "zip": "AutoComment-Pro.zip"}
    ]
    
    for p in products:
        download_url = f"https://github.com/{github_repo}/releases/download/{tag_name}/{p['zip']}"
        supabase.table("app_versions").upsert({
            "product_id": p["id"],
            "version": version,
            "download_url": download_url,
            "release_notes": f"⚡ {p['name']} 업그레이드 및 기능 개선 (v{version})"
        }).execute()
        
    print("Supabase DB records inserted.")
    print("OTA Deployment Pipeline finished successfully!")

if __name__ == "__main__":
    main()
