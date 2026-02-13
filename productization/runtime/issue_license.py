import argparse
from pathlib import Path

from license_runtime import (
    load_private_key,
    make_claims,
    save_text,
    sign_license,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="라이선스 발급기 (Ed25519 서명)")
    parser.add_argument("--product", required=True, help="제품 시스템 ID (예: CafeMonster_Crawler_Pro)")
    parser.add_argument("--cafe", required=True, help="카페 식별자/URL")
    parser.add_argument("--term", required=True, help="1m | 6m | 1y | permanent")
    parser.add_argument(
        "--private-key",
        default="productization/keys/ed25519_private.pem",
        help="개인키 경로",
    )
    parser.add_argument(
        "--out",
        default="license.lic",
        help="출력 라이선스 파일 경로",
    )
    args = parser.parse_args()

    private_key_path = Path(args.private_key)
    out_path = Path(args.out)

    claims = make_claims(args.product, args.cafe, args.term)
    token = sign_license(claims, load_private_key(private_key_path))
    save_text(out_path, token)

    print("[OK] license issued")
    print(f"  product : {claims.product}")
    print(f"  cafe    : {claims.cafe_key}")
    print(f"  term    : {args.term}")
    print(f"  lic_id  : {claims.license_id}")
    print(f"  out     : {out_path.resolve()}")


if __name__ == "__main__":
    main()
