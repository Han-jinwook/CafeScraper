from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


TOKEN_PREFIX = "LS1"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("utf-8"))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_cafe_key(value: str) -> str:
    """
    라이선스 바인딩용 카페 식별자 정규화.
    - https://cafe.naver.com/sundreamd -> sundreamd
    - https://cafe.naver.com/f-e/cafes/27870803/menus/0 -> 27870803
    """
    v = (value or "").strip()
    if not v:
        return ""

    try:
        u = urlparse(v)
        path = (u.path or "").strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            return parts[0].lower()
        if "cafes" in parts:
            i = parts.index("cafes")
            if i + 1 < len(parts):
                return parts[i + 1].lower()
    except Exception:
        pass
    return v.lower()


def resolve_target_cafe_key(config_path: Path) -> str:
    if not config_path.exists():
        return ""
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    cafe_url = str(cfg.get("cafe_url", "") or "")
    board_url = str(cfg.get("board_url", "") or "")
    return normalize_cafe_key(cafe_url) or normalize_cafe_key(board_url)


@dataclass
class LicenseClaims:
    product: str
    cafe_key: str
    issued_at: str
    expires_at: Optional[str]
    license_id: str
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "ver": self.version,
            "product": self.product,
            "cafe": self.cafe_key,
            "iat": self.issued_at,
            "exp": self.expires_at,
            "lic_id": self.license_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "LicenseClaims":
        return LicenseClaims(
            product=str(data.get("product", "")),
            cafe_key=str(data.get("cafe", "")),
            issued_at=str(data.get("iat", "")),
            expires_at=data.get("exp"),
            license_id=str(data.get("lic_id", "")),
            version=int(data.get("ver", 1)),
        )


def make_claims(product: str, cafe_key: str, term: str) -> LicenseClaims:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    exp: Optional[datetime] = None
    t = term.lower().strip()
    if t in ("1m", "1month", "month"):
        exp = now + timedelta(days=30)
    elif t in ("6m", "6month", "6months"):
        exp = now + timedelta(days=183)
    elif t in ("1y", "1year", "year"):
        exp = now + timedelta(days=365)
    elif t in ("permanent", "lifetime", "forever"):
        exp = None
    else:
        raise ValueError("term must be one of: 1m, 6m, 1y, permanent")

    return LicenseClaims(
        product=product,
        cafe_key=normalize_cafe_key(cafe_key),
        issued_at=now.isoformat(),
        expires_at=exp.isoformat() if exp else None,
        license_id=f"LIC-{uuid.uuid4().hex[:12].upper()}",
    )


def load_private_key(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    return serialization.load_pem_private_key(raw, password=None)


def load_public_key(path: Path) -> Ed25519PublicKey:
    raw = path.read_bytes()
    return serialization.load_pem_public_key(raw)


def generate_keypair(private_key_path: Path, public_key_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)


def sign_license(claims: LicenseClaims, private_key: Ed25519PrivateKey) -> str:
    payload_bytes = json.dumps(claims.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = private_key.sign(payload_bytes)
    return f"{TOKEN_PREFIX}.{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"


def verify_license_token(token: str, public_key: Ed25519PublicKey) -> LicenseClaims:
    parts = (token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise ValueError("invalid token format")

    payload = _b64url_decode(parts[1])
    sig = _b64url_decode(parts[2])
    try:
        public_key.verify(sig, payload)
    except InvalidSignature as e:
        raise ValueError("invalid signature") from e

    data = json.loads(payload.decode("utf-8"))
    return LicenseClaims.from_dict(data)


def validate_runtime(
    claims: LicenseClaims,
    expected_product: str,
    expected_cafe_key: str,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    if claims.product != expected_product:
        return False, f"제품 불일치: {claims.product} != {expected_product}"

    target = normalize_cafe_key(expected_cafe_key)
    if target and claims.cafe_key != target:
        return False, f"카페 불일치: {claims.cafe_key} != {target}"

    if claims.expires_at:
        now_dt = now or datetime.now(timezone.utc)
        try:
            exp_dt = datetime.fromisoformat(claims.expires_at)
        except Exception:
            return False, "라이선스 만료일 파싱 실패"
        if now_dt > exp_dt:
            return False, f"라이선스 만료: {claims.expires_at}"

    return True, "ok"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def save_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + os.linesep, encoding="utf-8")
