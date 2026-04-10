from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.utils.paths import get_config_path

NickKind = Literal["post", "comment"]
_MAX_PRESETS = 50


def get_event_nick_presets_path() -> Path:
    return get_config_path().parent / "event_nick_presets.json"


def load_event_nick_presets() -> dict[str, list[dict[str, Any]]]:
    p = get_event_nick_presets_path()
    if not p.is_file():
        return {"post": [], "comment": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: dict[str, list[dict[str, Any]]] = {
            "post": list(data.get("post") or []),
            "comment": list(data.get("comment") or []),
        }
        for k in ("post", "comment"):
            for row in out[k]:
                row.setdefault("name", "")
                row.setdefault("text", "")
                row.setdefault("saved_at", "")
        return out
    except Exception:
        return {"post": [], "comment": []}


def upsert_event_nick_preset(kind: NickKind, name: str, text: str) -> str:
    """
    같은 이름이 있으면 덮어씁니다. 최신이 목록 맨 위로 옵니다.
    반환: 실제로 저장된 표시 이름.
    """
    name = (name or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M")
    text = str(text or "")
    data = load_event_nick_presets()
    lst = list(data.get(kind) or [])
    lst = [r for r in lst if str(r.get("name") or "").strip() != name]
    lst.insert(
        0,
        {
            "name": name,
            "text": text,
            "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        },
    )
    data[kind] = lst[:_MAX_PRESETS]
    p = get_event_nick_presets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return name


def delete_event_nick_preset(kind: NickKind, name: str) -> None:
    name = (name or "").strip()
    if not name:
        return
    data = load_event_nick_presets()
    data[kind] = [r for r in (data.get(kind) or []) if str(r.get("name") or "").strip() != name]
    p = get_event_nick_presets_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
