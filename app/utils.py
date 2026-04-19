from datetime import datetime, timezone


def format_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_get(d: dict, *keys):
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
