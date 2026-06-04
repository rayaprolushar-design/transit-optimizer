"""
scripts/search.py
Fuzzy stop-name matching — lets users type "mg road" instead of exact "MG Road".

How it works:
  1. Exact match (case-insensitive) → score 100
  2. Starts-with match             → score 90
  3. Contains match                → score 75
  4. Token overlap (word by word)  → score proportional to overlap

No external libraries needed — pure Python string ops.
"""


def _normalize(s: str) -> str:
    return s.lower().strip()


def _score(query: str, candidate: str) -> int:
    q = _normalize(query)
    c = _normalize(candidate)

    if q == c:
        return 100
    if c.startswith(q):
        return 90
    if q in c:
        return 75

    # Token overlap score
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    overlap   = q_tokens & c_tokens
    if overlap:
        return int(60 * len(overlap) / max(len(q_tokens), len(c_tokens)))

    return 0


def fuzzy_find_stop(query: str, stops: dict,
                    threshold: int = 40) -> tuple[str | None, str | None, int]:
    """
    Find the best-matching stop for a query string.

    Returns:
        (stop_id, stop_name, score)  — stop_id is None if no match above threshold
    """
    best_id    = None
    best_name  = None
    best_score = 0

    for sid, data in stops.items():
        name  = data.get("name", "")
        score = _score(query, name)
        if score > best_score:
            best_score = score
            best_id    = sid
            best_name  = name

    if best_score < threshold:
        return None, None, 0

    return best_id, best_name, best_score
