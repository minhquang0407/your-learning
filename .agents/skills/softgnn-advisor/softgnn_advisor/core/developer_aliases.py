import json
from pathlib import Path


def _norm(value: str) -> str:
    return str(value or '').strip().lower()


def load_developer_aliases(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return {}
    return {_norm(k): str(v).strip() for k, v in raw.items() if str(v).strip()}


def resolve_developer_identity(name: str, email: str = '', aliases: dict | None = None) -> str:
    aliases = aliases or {}
    name_raw = str(name or '').strip()
    email_raw = str(email or '').strip()

    for key in (email_raw, name_raw, f'{name_raw} <{email_raw}>'):
        mapped = aliases.get(_norm(key))
        if mapped:
            return mapped

    return name_raw or email_raw or 'Unknown'
