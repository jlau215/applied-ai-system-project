"""
Lightweight local retriever for PawPal+'s RAG pipeline.

No external services or paid APIs required: markdown docs in
knowledge_base/docs/ are split into sections, indexed with a small TF-IDF
scorer built from the standard library only, and searched at query time.
This is the "R" in RAG -- retrieval happens locally and its results are
handed to the Gemini agent, which must use them to answer.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DOCS_DIR = Path(__file__).parent / "docs"

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common words filtered out so short queries aren't dominated by noise --
# with only a handful of docs, idf alone doesn't discriminate stopwords well.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "been", "being", "with", "at", "by",
    "this", "that", "these", "those", "it", "its", "as", "if", "so", "than",
    "then", "do", "does", "did", "not", "no", "can", "how", "what", "when",
    "where", "why", "which", "who", "i", "you", "your", "my", "their",
    "best", "good", "should", "would", "could", "will", "just", "about",
}


@dataclass
class Chunk:
    source: str   # filename, e.g. "pet_food.md"
    title: str    # section heading, e.g. "Puppy nutrition"
    text: str     # section body


def _stem(token: str) -> str:
    """Minimal suffix stripping so 'walking'/'walks' match 'walk', etc.

    Not a real linguistic stemmer -- just enough crude normalization for a
    small local corpus where exact-match TF-IDF would otherwise miss
    obvious plural/gerund variants.
    """
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _tokenize(text: str) -> list[str]:
    return [
        _stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS
    ]


def _load_chunks() -> list[Chunk]:
    """Split every markdown file in docs/ into '## '-delimited sections."""
    chunks: list[Chunk] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
        for section in sections[1:]:  # sections[0] is the '# Title' preamble
            title, _, body = section.partition("\n")
            chunks.append(Chunk(source=path.name, title=title.strip(), text=body.strip()))
    return chunks


class _Index:
    """TF-IDF index over the chunk corpus, built once and cached."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._chunk_tokens = [_tokenize(f"{c.title} {c.text}") for c in chunks]

        doc_freq: dict[str, int] = {}
        for tokens in self._chunk_tokens:
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1

        n_docs = max(len(chunks), 1)
        self._idf = {
            token: math.log((n_docs + 1) / (freq + 1)) + 1
            for token, freq in doc_freq.items()
        }

    def search(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        scored: list[tuple[Chunk, float]] = []
        for chunk, tokens in zip(self.chunks, self._chunk_tokens):
            if not tokens:
                continue
            token_counts: dict[str, int] = {}
            for t in tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            score = 0.0
            for q in query_tokens:
                if q in token_counts:
                    tf = token_counts[q] / len(tokens)
                    score += tf * self._idf.get(q, 0.0)

            if score > 0:
                scored.append((chunk, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


_index: Optional[_Index] = None


def _get_index() -> _Index:
    global _index
    if _index is None:
        _index = _Index(_load_chunks())
    return _index


def retrieve(query: str, top_k: int = 3) -> list[Chunk]:
    """Return the top_k most relevant knowledge-base chunks for `query`.

    Returns an empty list if nothing scores above zero (e.g. an
    out-of-domain question) -- callers should fall back to the model's
    general knowledge and say so, rather than fabricate a source.
    """
    results = _get_index().search(query, top_k=top_k)
    return [chunk for chunk, _score in results]
