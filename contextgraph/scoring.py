"""BM25 scoring for recall queries."""

from __future__ import annotations

import math
from collections import defaultdict

from .utils import tokenize


class BM25Scorer:
    """Okapi BM25 scorer with incremental update support.

    Parameters
    ----------
    k1 : float
        Term frequency saturation parameter (default 1.5).
    b : float
        Length normalization parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

        # doc_id -> list of tokens
        self._doc_tokens: dict[str, list[str]] = {}
        # term -> set of doc_ids containing that term
        self._inverted_index: defaultdict[str, set[str]] = defaultdict(set)
        # total token count across all documents
        self._total_tokens: int = 0

    @property
    def _doc_count(self) -> int:
        return len(self._doc_tokens)

    @property
    def _avgdl(self) -> float:
        if self._doc_count == 0:
            return 0.0
        return self._total_tokens / self._doc_count

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def add_document(self, doc_id: str, text: str) -> None:
        """Add or replace a document in the index."""
        # Remove old version if updating
        if doc_id in self._doc_tokens:
            self.remove_document(doc_id)

        tokens = tokenize(text)
        self._doc_tokens[doc_id] = tokens
        self._total_tokens += len(tokens)

        for token in set(tokens):
            self._inverted_index[token].add(doc_id)

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the index."""
        tokens = self._doc_tokens.pop(doc_id, None)
        if tokens is None:
            return
        self._total_tokens -= len(tokens)
        for token in set(tokens):
            self._inverted_index[token].discard(doc_id)
            if not self._inverted_index[token]:
                del self._inverted_index[token]

    def has_document(self, doc_id: str) -> bool:
        return doc_id in self._doc_tokens

    def clear(self) -> None:
        self._doc_tokens.clear()
        self._inverted_index.clear()
        self._total_tokens = 0

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _idf(self, term: str) -> float:
        """Compute IDF for a single term."""
        n = self._doc_count
        if n == 0:
            return 0.0
        df = len(self._inverted_index.get(term, set()))
        # Standard BM25 IDF with floor at 0 to avoid negative values
        return max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))

    def score(self, doc_id: str, query: str) -> float:
        """Score a single document against a query.

        Returns 0.0 if the document is not in the index or has no
        matching terms.
        """
        tokens = self._doc_tokens.get(doc_id)
        if tokens is None:
            return 0.0

        doc_len = len(tokens)
        avgdl = self._avgdl
        if avgdl == 0:
            return 0.0

        # Build term-frequency map for this document
        tf_map: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf_map[t] += 1

        query_terms = tokenize(query)
        total = 0.0
        for qt in query_terms:
            idf = self._idf(qt)
            if idf == 0.0:
                continue
            f = tf_map.get(qt, 0)
            if f == 0:
                continue
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
            total += idf * (numerator / denominator)

        return total

    def score_text(self, query: str, text: str) -> float:
        """Score arbitrary text against a query without adding it to the index.

        Uses the current corpus statistics (avgdl, IDF) but does not
        require the text to be indexed.  Useful for one-off scoring.
        """
        tokens = tokenize(text)
        if not tokens:
            return 0.0

        doc_len = len(tokens)
        avgdl = self._avgdl
        if avgdl == 0:
            # Fallback: treat doc_len as avgdl when corpus is empty
            avgdl = float(doc_len)

        tf_map: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf_map[t] += 1

        query_terms = tokenize(query)
        total = 0.0
        for qt in query_terms:
            idf = self._idf(qt)
            if idf == 0.0:
                # When corpus is empty, give a small default IDF
                if self._doc_count == 0:
                    idf = 1.0
                else:
                    continue
            f = tf_map.get(qt, 0)
            if f == 0:
                continue
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
            total += idf * (numerator / denominator)

        return total
