from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import re
import secrets
from typing import Any
import uuid


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def new_api_key() -> str:
    """Generate a cryptographically secure API key (256 bits of entropy)."""
    return f"cgk_{secrets.token_urlsafe(32)}"


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def jaccard_similarity(a: str, b: str) -> float:
    left = set(tokenize(a))
    right = set(tokenize(b))
    if not left or not right:
        return 0.0
    intersection = left & right
    union = left | right
    return len(intersection) / len(union)


def pairwise(values: Iterable[str]) -> list[tuple[str, str]]:
    items = list(values)
    pairs: list[tuple[str, str]] = []
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            pairs.append((left, right))
    return pairs


def to_jsonable(value: Any) -> Any:
    from dataclasses import asdict, is_dataclass
    from enum import Enum

    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value

