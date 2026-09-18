from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence


DIMENSIONS = 128


def tokenize(text: str) -> list[str]:
    latin = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
    chinese = [
        text[i : i + 2]
        for i in range(len(text) - 1)
        if "\u4e00" <= text[i] <= "\u9fff" and "\u4e00" <= text[i + 1] <= "\u9fff"
    ]
    return latin + chinese


def embed_text(text: str) -> list[float]:
    """Deterministic local feature-hash embedding; replace with an approved model in production."""
    vector = [0.0] * DIMENSIONS
    for token in tokenize(text):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: Sequence[float] | None, right: Sequence[float]) -> float:
    # pgvector returns a NumPy array on PostgreSQL. Its truth value is
    # intentionally ambiguous, so never use ``if not left`` here.
    if left is None or len(left) == 0:
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right))
