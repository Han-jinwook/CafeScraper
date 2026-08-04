import os
import sys
import time
import shutil
import subprocess
import re
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

import ctypes

def get_short_path_name(long_name):
    needed = ctypes.windll.kernel32.GetShortPathNameW(long_name, None, 0)
    if needed == 0:
        return long_name
    buffer = ctypes.create_unicode_buffer(needed)
    ctypes.windll.kernel32.GetShortPathNameW(long_name, buffer, needed)
    return buffer.value

def find_chrome_path():
    # Candidates for chrome.exe
    candidates = []
    if os.name == "nt":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pfx86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        la = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(pf, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(pfx86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(la, r"Google\Chrome\Application\chrome.exe") if la else "",
        ]
        w = shutil.which("chrome") or shutil.which("chrome.exe")
        if w:
            candidates.append(w)
            
    for exe in candidates:
        if exe and os.path.isfile(exe):
            return get_short_path_name(exe)
    return None

def launch_chrome_via_schtasks(chrome_path, port=9222):
    task_name = "CafeScraper_Chrome_Interactive"
    user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\CafeScraper\chrome_profile_interactive")
    os.makedirs(user_data_dir, exist_ok=True)
    user_data_dir_short = get_short_path_name(user_data_dir)
    
    # Arguments - with no quotes needed because we use short paths!
    cmd = f'{chrome_path} --remote-debugging-port={port} --user-data-dir={user_data_dir_short} --window-size=1200,900'
    
    # 1. Clean existing task
    subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)
    
    # 2. Create task
    create_cmd = f'schtasks /create /tn "{task_name}" /tr "{cmd}" /sc once /sd 2026/01/01 /st 00:00 /ru "%USERNAME%" /it /f'
    print(f"Creating task with short paths: {create_cmd}")
    res_create = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
    if res_create.returncode != 0:
        print(f"Failed to create task: {res_create.stderr}")
        return False
        
    # 3. Run task
    print("Running task...")
    res_run = subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True, text=True)
    if res_run.returncode != 0:
        print(f"Failed to run task: {res_run.stderr}")
        return False
        
    # 4. Clean task definition
    subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)
    return True

def wait_for_chrome(port=9222, timeout=10):
    url = f"http://127.0.0.1:{port}/json/version"
    start_time = time.time()
    print("Waiting for Chrome debugging port to open...")
    while time.time() - start_time < timeout:
        try:
            res = requests.get(url, timeout=1)
            if res.status_code == 200:
                print("Chrome debugging port is active!")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("Timeout waiting for Chrome port.")
    return False

def _detect_installed_chrome_major_version():
    if os.name == "nt":
        try:
            import winreg
            for hive, path in (
                (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Google\Chrome\BLBeacon"),
            ):
                try:
                    with winreg.OpenKey(hive, path) as k:
                        ver, _ = winreg.QueryValueEx(k, "version")
                    major = int(str(ver).split(".")[0])
                    if 90 <= major <= 200:
                        return major
                except OSError:
                    continue
        except Exception:
            pass
    return None

def main():
    chrome_path = find_chrome_path()
    if not chrome_path:
        print("Chrome execution path not found.")
        sys.exit(1)
        
    print(f"Found Chrome: {chrome_path}")
    
    port = 9222
    if not launch_chrome_via_schtasks(chrome_path, port):
        print("Failed to launch Chrome via schtasks.")
        sys.exit(1)
        
    if not wait_for_chrome(port):
        print("Chrome did not start debugging port in time.")
        sys.exit(1)
        
    print("Connecting undetected_chromedriver...")
    options = uc.ChromeOptions()
    options.debugger_address = f"127.0.0.1:{port}"
    
    _vm = _detect_installed_chrome_major_version()
    print(f"Detected Chrome Major Version: {_vm}")
    
    try:
        _kw = {"options": options, "use_subprocess": True}
        if _vm is not None:
            _kw["version_main"] = _vm
        driver = uc.Chrome(**_kw)
        print("Connected successfully!")
        print(f"Current URL: {driver.current_url}")
        driver.get("https://naver.com")
        print(f"Navigated URL: {driver.current_url}")
        time.sleep(5)
        driver.quit()
        print("Test finished successfully!")
    except Exception as e:
        print(f"Failed to connect or control via undetected_chromedriver: {e}")

if __name__ == "__main__":
    main()
