from pathlib import Path

from license_runtime import generate_keypair


def main() -> None:
    out_dir = Path("productization/keys")
    private_key = out_dir / "ed25519_private.pem"
    public_key = out_dir / "ed25519_public.pem"
    generate_keypair(private_key, public_key)
    print(f"[OK] private key: {private_key}")
    print(f"[OK] public key : {public_key}")


if __name__ == "__main__":
    main()
