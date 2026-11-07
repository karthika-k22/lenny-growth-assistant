from backend.rag import build_index, search_transcripts


def test_search_returns_relevant_knowledge():
    build_index()

    results = search_transcripts("product growth", top_k=4)

    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["source"] == "product_growth_fundamentals.md"
    assert "episode" in results[0]
    assert "text" in results[0]


def test_search_respects_top_k():
    build_index()

    results = search_transcripts("product growth", top_k=2)

    assert len(results) <= 2


def test_search_empty_query_returns_no_results():
    results = search_transcripts("")

    assert results == []


def test_search_irrelevant_query_returns_no_results():
    results = search_transcripts("xyzqv987654unlikelyterm")

    assert results == []