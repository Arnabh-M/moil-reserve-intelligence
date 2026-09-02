"""Text -> embedding vector, behind one interface.

`Embedder.embed(text) -> list[float]` (length `EMBEDDING_DIM`, L2-normalised)
is the only contract the site-notes route and the `site_notes.embedding`
column depend on.

The default `HashingEmbedder` is fully deterministic and local — no model
download, no API key, no network. It's a hashed bag-of-(stemmed) words +
bigrams projected into a fixed-width space; good enough that a query like
"monsoon flooding" ranks a note about "heavy rain waterlogging the haul
road" above an unrelated one. Swap `get_embedder()` for a
sentence-transformers / API-backed implementation later — as long as it
returns `EMBEDDING_DIM` floats, nothing else changes (the DB column width
is pinned to this constant by the migration).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

EMBEDDING_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    """
    a an and are as at be by для for from has have in into is it its of on or
    that the their then there these this to was were will with within
    """.split()
)


def _stem(token: str) -> str:
    for suffix in ("ing", "edly", "ed", "ly", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    raw = [_stem(t) for t in _TOKEN_RE.findall(text.lower())]
    return [t for t in raw if t and t not in _STOPWORDS]


def _bucket(feature: str) -> int:
    digest = hashlib.sha1(feature.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") % EMBEDDING_DIM


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


def _char_ngrams(token: str, n: int) -> list[str]:
    padded = f"^{token}$"
    if len(padded) < n:
        return [padded]
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


class HashingEmbedder:
    """Deterministic hashed features, L2-normalised:

      - whole (stemmed) tokens            weight 1.0
      - token bigrams                     weight 0.5  (some word-order signal)
      - per-token character 3- and 4-grams weight 0.28 (morphology: so
        "intercept"~"intersected", "pump"~"pumping" partially align even
        though this isn't a semantic model)
    """

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        toks = _tokens(text)
        for tok in toks:
            vec[_bucket(tok)] += 1.0
            for n in (3, 4):
                for g in _char_ngrams(tok, n):
                    vec[_bucket(f"#{n}:{g}")] += 0.28
        for a, b in zip(toks, toks[1:]):
            vec[_bucket(f"{a}_{b}")] += 0.5

        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            # No usable tokens (empty / punctuation-only / all stopwords).
            # A tiny deterministic non-zero vector keeps cosine distance
            # defined rather than NaN.
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]


def get_embedder() -> Embedder:
    """Return the active embedder. Single swap-point for a real model/API."""
    return HashingEmbedder()
