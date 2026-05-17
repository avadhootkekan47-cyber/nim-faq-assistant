"""
src/faq/loader.py
─────────────────
Loads FAQ entries from a YAML file.
To switch to a database later, replace _load_from_yaml() with a DB query
and keep the same FAQItem / FAQStore interface.
"""

import math
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config import settings


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class FAQItem:
    id: str
    category: str
    question: str
    answer: str
    tags: list[str] = field(default_factory=list)


# ── Loader ────────────────────────────────────────────────────────────────────

class FAQStore:
    """
    In-memory FAQ store with simple TF-IDF-style cosine similarity search.
    Call .load() once at startup; it is synchronous and fast for <10k entries.
    """

    def __init__(self):
        self._items: list[FAQItem] = []
        self._corpus_tf: list[dict[str, float]] = []   # term frequencies per doc
        self._idf: dict[str, float] = {}               # inverse document frequency

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self, path: Optional[str] = None) -> None:
        """Load FAQs from YAML. Call at app startup."""
        faq_path = Path(path or settings.faq_file)
        if not faq_path.exists():
            raise FileNotFoundError(f"FAQ file not found: {faq_path}")
        self._items = _load_from_yaml(faq_path)
        self._build_index()

    def search(self, query: str, top_k: Optional[int] = None) -> list[FAQItem]:
        """
        Return the top_k most relevant FAQ items for a query.
        Uses TF-IDF cosine similarity on (question + tags) text.
        """
        k = top_k or settings.faq_top_k
        if not self._items:
            return []

        q_vec = self._vectorise(query)
        scored = []
        for i, item in enumerate(self._items):
            score = _cosine(q_vec, self._corpus_tf[i], self._idf)
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:k] if score > 0]

    def get_by_id(self, faq_id: str) -> Optional[FAQItem]:
        return next((i for i in self._items if i.id == faq_id), None)

    def all_items(self) -> list[FAQItem]:
        return list(self._items)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_index(self) -> None:
        """Compute TF and IDF for all FAQ questions + tags."""
        N = len(self._items)
        self._corpus_tf = []
        df: dict[str, int] = {}

        for item in self._items:
            text = f"{item.question} {' '.join(str(t) for t in item.tags)}"
            tokens = _tokenise(text)
            tf = _term_freq(tokens)
            self._corpus_tf.append(tf)
            for term in tf:
                df[term] = df.get(term, 0) + 1

        # Smooth IDF: log((N+1)/(df+1)) + 1
        self._idf = {
            term: math.log((N + 1) / (count + 1)) + 1
            for term, count in df.items()
        }

    def _vectorise(self, text: str) -> dict[str, float]:
        tokens = _tokenise(text)
        return _term_freq(tokens)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_from_yaml(path: Path) -> list[FAQItem]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    items = []
    for raw in data.get("faqs", []):
        items.append(FAQItem(
            id=raw["id"],
            category=raw.get("category", "general"),
            question=raw["question"],
            answer=raw["answer"].strip(),
            tags=raw.get("tags", []),
        ))
    return items


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _term_freq(tokens: list[str]) -> dict[str, float]:
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(tokens) or 1
    return {t: c / total for t, c in tf.items()}


def _cosine(
    q: dict[str, float],
    doc: dict[str, float],
    idf: dict[str, float],
) -> float:
    """Cosine similarity between query and doc TF vectors, weighted by IDF."""
    dot = sum(
        q.get(term, 0) * doc.get(term, 0) * idf.get(term, 1.0)
        for term in set(q) | set(doc)
    )
    mag_q = math.sqrt(sum((v * idf.get(t, 1)) ** 2 for t, v in q.items()))
    mag_d = math.sqrt(sum((v * idf.get(t, 1)) ** 2 for t, v in doc.items()))
    if mag_q == 0 or mag_d == 0:
        return 0.0
    return dot / (mag_q * mag_d)


# ── Module-level singleton ─────────────────────────────────────────────────────
# Populated in main.py during app startup via faq_store.load()
faq_store = FAQStore()
