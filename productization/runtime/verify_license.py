import argparse
import json
import sys
from pathlib import Path

from license_runtime import (
    load_public_key,
    load_text,
    resolve_target_cafe_key,
    validate_runtime,
    verify_license_token,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="라이선스 검증기")
    parser.add_argument("--product", required=True, help="제품 키")
    parser.add_argument("--license-file", default="license.lic", help="라이선스 파일 경로")
    parser.add_argument("--public-key", default="ed25519_public.pem", help="공개키 파일 경로")
    parser.add_argument("--config", default="user_settings.json", help="설정 파일 경로")
    args = parser.parse_args()

    lic_path = Path(args.license_file)
    pub_path = Path(args.public_key)
    cfg_path = Path(args.config)

    if not lic_path.exists():
        print("[FAIL] license file not found")
        return 2
    if not pub_path.exists():
        print("[FAIL] public key not found")
        return 3

    token = load_text(lic_path)
    claims = verify_license_token(token, load_public_key(pub_path))
    target_cafe_key = resolve_target_cafe_key(cfg_path)
    ok, msg = validate_runtime(claims, args.product, target_cafe_key)
    result = {
        "ok": ok,
        "message": msg,
        "product": claims.product,
        "cafe": claims.cafe_key,
        "expires_at": claims.expires_at,
        "license_id": claims.license_id,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
