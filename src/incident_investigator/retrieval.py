"""Dense + BM25 retrieval, stable-ID deduplication, RRF, optional local rerank."""
import tomllib
import time

from .providers import ROOT
from .pinecone_store import semantic_search, keyword_search
from .reranking import rerank


def retrieval_config():
    return tomllib.loads((ROOT / "config/retrieval.toml").read_text())


def reciprocal_rank_fusion(semantic, keyword, k=60, limit=10):
    """RRF(d) = sum(1/(k + rank(d))); one vote per ID per retrieval list."""
    if k <= 0 or limit <= 0:
        raise ValueError("RRF k and limit must be positive")
    combined = {}
    for channel, rows in (("semantic", semantic), ("keyword", keyword)):
        seen = set()
        for row in rows:
            identifier = row["id"]
            if identifier in seen:
                continue
            seen.add(identifier)
            rank = len(seen)
            entry = combined.setdefault(identifier, {**row, "rrf_score": 0.0, "retrieval_ranks": {}, "retrieval_scores": {}})
            entry["rrf_score"] += 1.0 / (k + rank)
            entry["retrieval_ranks"][channel] = rank
            entry["retrieval_scores"][channel] = row.get("score")
    result = sorted(combined.values(), key=lambda row: (-row["rrf_score"], row["id"]))[:limit]
    return [{**row, "fusion_rank": rank} for rank, row in enumerate(result, 1)]


def hybrid_search(description, use_reranker=None):
    started = time.perf_counter()
    if not isinstance(description, str) or not description.strip():
        return {"results": [], "error": "Enter a non-empty incident description.", "reranking": {"active": False}}
    cfg = retrieval_config()
    if use_reranker is not None:
        cfg["reranking_enabled"] = use_reranker
    phase = time.perf_counter()
    semantic = semantic_search(description, top_k=cfg["candidate_limit"])
    semantic_seconds = time.perf_counter() - phase
    phase = time.perf_counter()
    keyword = keyword_search(description, top_k=cfg["candidate_limit"])
    keyword_seconds = time.perf_counter() - phase
    warnings = [f"{name}: {result['error']}" for name, result in (("semantic", semantic), ("keyword", keyword)) if result.get("error")]
    if semantic.get("error") and keyword.get("error"):
        return {"results": [], "error": "Both retrieval branches failed.", "warnings": warnings, "reranking": {"active": False}}
    phase = time.perf_counter()
    candidates = reciprocal_rank_fusion(semantic["results"], keyword["results"], cfg["rrf_k"], cfg["candidate_limit"])
    fusion_seconds = time.perf_counter() - phase
    phase = time.perf_counter()
    ordered, status = rerank(description, candidates, cfg)
    reranking_seconds = time.perf_counter() - phase
    results = []
    for rank, row in enumerate(ordered[:cfg["result_limit"]], 1):
        results.append({**row, "rank": rank,
                        "score": row["rerank_score"] if status["active"] else row["rrf_score"],
                        "score_type": "cross_encoder_logit" if status["active"] else "rrf"})
    return {"query": description, "results": results, "candidate_count": len(candidates),
            "retrieval_counts": {"semantic": len(semantic["results"]), "keyword": len(keyword["results"])},
            "fusion": {"method": "RRF", "k": cfg["rrf_k"]}, "reranking": status, "warnings": warnings, "error": None,
            "timings": {"semantic_seconds": round(semantic_seconds, 4), "keyword_seconds": round(keyword_seconds, 4),
                        "fusion_seconds": round(fusion_seconds, 4), "reranking_seconds": round(reranking_seconds, 4),
                        "total_seconds": round(time.perf_counter() - started, 4)}}
