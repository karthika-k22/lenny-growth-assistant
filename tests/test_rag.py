import pytest

from backend.rag import build_index, search_transcripts


@pytest.fixture(scope="module", autouse=True)
def prepare_index():
    build_index()


@pytest.mark.parametrize(
    "query, expected_source",
    [
        ("How can we reduce customer churn?", "product_growth_fundamentals.md"),
        ("How do marketplaces attract buyers and sellers?", "product_growth.txt"),
        ("What makes A/B testing effective?", "product_growth.txt"),
        ("How can a company improve customer retention?", "product_growth_fundamentals.md"),
        ("How should product teams prioritize work?", "product_growth_fundamentals.md"),
        ("How did Etsy grow its marketplace?", "product_growth.txt"),
    ],
)
def test_search_returns_relevant_source(query, expected_source):
    results = search_transcripts(query, top_k=3)

    assert results
    assert expected_source in [result["source"] for result in results]


def test_search_respects_top_k():
    results = search_transcripts("product growth", top_k=2)

    assert len(results) <= 2


def test_search_empty_query_returns_no_results():
    assert search_transcripts("") == []


def test_search_irrelevant_query_returns_no_results():
    assert search_transcripts("xyzqv987654unlikelyterm") == []


@pytest.mark.parametrize("top_k", [0, -1, True, "4", None])
def test_search_rejects_invalid_top_k(top_k):
    assert search_transcripts("product growth", top_k=top_k) == []
