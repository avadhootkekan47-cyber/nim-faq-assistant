"""
tests/test_faq.py
─────────────────
Basic tests for the FAQ loader and search logic.
Run with: pytest tests/ -v
"""

import pytest
from pathlib import Path

from src.faq.loader import FAQStore


FAQ_YAML = """
faqs:
  - id: test-001
    category: pricing
    tags: [pricing, cost]
    question: How much does the Pro plan cost?
    answer: The Pro plan costs $29 per month.

  - id: test-002
    category: account
    tags: [password, reset]
    question: How do I reset my password?
    answer: Click Forgot Password on the login page.

  - id: test-003
    category: technical
    tags: [api, key]
    question: How do I get my API key?
    answer: Go to Dashboard and create a new API key.
"""


@pytest.fixture
def store(tmp_path: Path) -> FAQStore:
    faq_file = tmp_path / "faq.yml"
    faq_file.write_text(FAQ_YAML)
    s = FAQStore()
    s.load(str(faq_file))
    return s


def test_load_count(store: FAQStore):
    assert len(store.all_items()) == 3


def test_search_pricing(store: FAQStore):
    results = store.search("how much does the plan cost", top_k=1)
    assert results, "Should return at least one match"
    assert results[0].id == "test-001"


def test_search_password(store: FAQStore):
    results = store.search("reset my password", top_k=1)
    assert results
    assert results[0].id == "test-002"


def test_search_no_match(store: FAQStore):
    results = store.search("xyzzy frobnicator quantum flux", top_k=3)
    # May return empty or low-quality matches — that's fine
    # Just ensure it doesn't crash
    assert isinstance(results, list)


def test_get_by_id(store: FAQStore):
    item = store.get_by_id("test-003")
    assert item is not None
    assert item.category == "technical"


def test_get_by_id_missing(store: FAQStore):
    assert store.get_by_id("nonexistent") is None
