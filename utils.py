import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def timestamp_to_iso(value) -> str | None:
    if value is None:
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if numeric > 10_000_000_000:
        numeric = numeric / 1000
    return datetime.fromtimestamp(numeric, timezone.utc).replace(microsecond=0).isoformat()


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def truncate_text(value, limit=1200):
    if value is None:
        return None
    value = str(value)
    return value if len(value) <= limit else value[:limit].rstrip() + "..."


def extract_forum_id(value: str) -> str:
    parsed = urlparse(value)
    if parsed.query:
        query = parse_qs(parsed.query)
        for key in ("id", "forum", "noteId"):
            if query.get(key):
                return query[key][0]
    candidate = value.strip()
    if "/" not in candidate and " " not in candidate:
        return candidate
    raise ValueError("Could not find an OpenReview forum id in that URL.")


def content_value(content: dict, *names: str):
    for name in names:
        value = content.get(name)
        if isinstance(value, dict) and "value" in value:
            return value["value"]
        if value is not None:
            return value
    return None


def db_text(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
