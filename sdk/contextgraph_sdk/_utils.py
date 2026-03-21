from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(value.lower())


def jaccard_similarity(a: str, b: str) -> float:
    left = set(_tokenize(a))
    right = set(_tokenize(b))
    if not left or not right:
        return 0.0
    intersection = left & right
    union = left | right
    return len(intersection) / len(union)
