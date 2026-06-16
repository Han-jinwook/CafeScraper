from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import webview

from license_runtime import (
    load_public_key,
    load_text,
    resolve_target_cafe_key,
    validate_runtime,
    verify_license_token,
)


def find_free_port(start: int = 8650, end: int = 8899) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("사용 가능한 포트를 찾지 못했습니다.")


def wait_server_ready(url: str, timeout_sec: int = 45) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(url, timeout=1.5)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.6)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="제품용 데스크톱 런처")
    parser.add_argument("--product", required=True, help="제품 키")
    parser.add_argument("--entry", required=True, help="Streamlit 엔트리 파일")
    parser.add_argument("--title", required=True, help="창 제목")
    parser.add_argument("--license-file", default="license.lic")
    parser.add_argument("--public-key", default="ed25519_public.pem")
    parser.add_argument("--config", default="user_settings.json")
    args = parser.parse_args()

    root = Path.cwd()
    lic_path = root / args.license_file
    pub_path = root / args.public_key
    cfg_path = root / args.config

    if not lic_path.exists() or not pub_path.exists():
        print("[FAIL] license/public key 파일이 없습니다.")
        print("대한민국 No.1 카페 마케팅의 괴물, 카페 몬스터의 시리얼 번호를 입력하세요.")
        return 2

    try:
        claims = verify_license_token(load_text(lic_path), load_public_key(pub_path))
        target_cafe = resolve_target_cafe_key(cfg_path)
        ok, msg = validate_runtime(claims, args.product, target_cafe)
        if not ok:
            print("[FAIL] license invalid:", msg)
            print("대한민국 No.1 카페 마케팅의 괴물, 카페 몬스터의 시리얼 번호를 입력하세요.")
            return 3
    except Exception as e:
        print("[FAIL] license verify error:", e)
        print("대한민국 No.1 카페 마케팅의 괴물, 카페 몬스터의 시리얼 번호를 입력하세요.")
        return 4

    port = find_free_port()
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        args.entry,
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    proc = subprocess.Popen(streamlit_cmd, cwd=str(root))
    app_url = f"http://127.0.0.1:{port}"

    if not wait_server_ready(app_url):
        proc.terminate()
        print("[FAIL] streamlit server 시작 실패")
        return 5

    window = webview.create_window(args.title, app_url, width=1360, height=900)
    try:
        webview.start(gui="edgechromium")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
