from collections.abc import Sequence


def _normalize_id(value: object) -> str:
    return str(value).strip()


def recall_at_k(expected_ids: Sequence[object], retrieved_ids: Sequence[object], k: int) -> float:
    expected = {_normalize_id(item) for item in expected_ids if _normalize_id(item)}
    if not expected:
        return 0.0
    retrieved = {_normalize_id(item) for item in retrieved_ids[:k] if _normalize_id(item)}
    return len(expected & retrieved) / len(expected)


def precision_at_k(expected_ids: Sequence[object], retrieved_ids: Sequence[object], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be greater than 0")
    retrieved = [_normalize_id(item) for item in retrieved_ids[:k] if _normalize_id(item)]
    if not retrieved:
        return 0.0
    expected = {_normalize_id(item) for item in expected_ids if _normalize_id(item)}
    return len(expected & set(retrieved)) / min(k, len(retrieved_ids))


def mrr(expected_ids: Sequence[object], retrieved_ids: Sequence[object]) -> float:
    expected = {_normalize_id(item) for item in expected_ids if _normalize_id(item)}
    if not expected:
        return 0.0
    for rank, retrieved_id in enumerate(retrieved_ids, start=1):
        if _normalize_id(retrieved_id) in expected:
            return 1.0 / rank
    return 0.0


def required_term_coverage(required_terms: Sequence[str], texts: Sequence[str]) -> float:
    terms = [term.strip() for term in required_terms if term and term.strip()]
    if not terms:
        return 0.0
    haystack = "\n".join(texts)
    matched = sum(1 for term in terms if term in haystack)
    return matched / len(terms)


def page_recall(expected_pages: Sequence[int], retrieved_pages: Sequence[int]) -> float:
    expected = {int(page) for page in expected_pages}
    if not expected:
        return 0.0
    retrieved = {int(page) for page in retrieved_pages}
    return len(expected & retrieved) / len(expected)


def citation_correctness(expected_pages: Sequence[int], citations: Sequence[dict]) -> float:
    cited_pages = []
    for citation in citations:
        page = citation.get("page_number") or citation.get("page")
        if page is not None:
            cited_pages.append(int(page))
    return page_recall(expected_pages, cited_pages)


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
