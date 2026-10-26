"""Behavior checks for BM25 requests, RRF, deduplication, and rerank fallback."""
import unittest
from unittest.mock import MagicMock, patch

from pinecone import SearchDocumentsResponse
from src.incident_investigator import pinecone_store as store
from src.incident_investigator import retrieval
from src.incident_investigator.reranking import rerank


def passage(identifier):
    return {"id": identifier, "incident_id": identifier, "title": "Incident",
            "source": "data/incidents/synthetic/SYN-001.json", "source_type": "synthetic",
            "source_url": None, "chunk_text": "HTTP 503 errors after deployment", "score": 0.7}


class RetrievalTests(unittest.TestCase):
    def test_keyword_uses_verified_text_query_and_keeps_metadata(self):
        index = MagicMock()
        hit = {**passage("SYN-001:chunk:001"), "_id": "SYN-001:chunk:001", "_score": 8.0}
        index.documents.search.return_value = SearchDocumentsResponse.from_dict({"matches": [hit]})
        with patch.object(store, "local_records", return_value=([], {"model": "offline-fixture"}, {})), patch.object(store, "open_index", return_value=index), patch.object(store, "embedding_provider") as provider:
            result = store.keyword_search("HTTP 503")
            self.assertIsNone(result["error"])
            self.assertIn("503", result["results"][0]["chunk_text"])
            clause = index.documents.search.call_args.kwargs["score_by"][0]
            self.assertEqual(clause.query, "HTTP 503")
            self.assertEqual(clause.fields, ["chunk_text"])
            provider.assert_not_called()

    def test_rrf_duplicates_receive_one_vote_per_branch(self):
        results = retrieval.reciprocal_rank_fusion(
            [passage("a"), passage("a"), passage("b")], [passage("b"), passage("a")])
        self.assertEqual(len(results), 2)
        self.assertAlmostEqual(results[0]["rrf_score"], 1 / 61 + 1 / 62)
        self.assertEqual(results[0]["id"], "a")
        self.assertEqual(results[0]["retrieval_ranks"], {"semantic": 1, "keyword": 2})
        self.assertEqual(retrieval.reciprocal_rank_fusion([], []), [])

    def test_candidate_cap_and_top_five(self):
        semantic = {"results": [passage(str(i)) for i in range(10)], "error": None}
        keyword = {"results": [passage(str(i)) for i in range(5, 15)], "error": None}
        with patch.object(retrieval, "semantic_search", return_value=semantic) as dense, patch.object(retrieval, "keyword_search", return_value=keyword):
            result = retrieval.hybrid_search("HTTP 503", use_reranker=False)
        self.assertEqual(result["candidate_count"], 10)
        self.assertEqual(len(result["results"]), 5)
        self.assertEqual(len({r["id"] for r in result["results"]}), 5)
        self.assertFalse(result["reranking"]["active"])
        dense.assert_called_once_with("HTTP 503", top_k=10)

    def test_empty_and_partial_failure(self):
        empty = {"results": [], "error": None}
        failure = {"results": [], "error": "Unavailable"}
        with patch.object(retrieval, "semantic_search", return_value=empty), patch.object(retrieval, "keyword_search", return_value=empty):
            self.assertEqual(retrieval.hybrid_search("unknown")["results"], [])
        with patch.object(retrieval, "semantic_search", return_value=failure), patch.object(retrieval, "keyword_search", return_value={"results": [passage("a")], "error": None}):
            result = retrieval.hybrid_search("HTTP 503", use_reranker=False)
            self.assertEqual(len(result["results"]), 1)
            self.assertTrue(result["warnings"])
        with patch.object(retrieval, "semantic_search", return_value=failure), patch.object(retrieval, "keyword_search", return_value=failure):
            self.assertTrue(retrieval.hybrid_search("HTTP 503")["error"])
        self.assertTrue(retrieval.hybrid_search(" ")["error"])

    def test_reranker_failure_retains_rrf_order(self):
        candidates = retrieval.reciprocal_rank_fusion([passage("a")], [])
        cfg = retrieval.retrieval_config()
        cfg["reranker_path"] = "data/nonexistent-reranker"
        result, status = rerank("HTTP 503", candidates, cfg)
        self.assertFalse(status["active"])
        self.assertEqual(result, candidates)

    def test_reranker_order_is_used(self):
        rows = retrieval.reciprocal_rank_fusion([passage("a"), passage("b")], [])
        reordered = [{**rows[1], "rerank_score": 2.0}, {**rows[0], "rerank_score": -1.0}]
        with patch.object(retrieval, "semantic_search", return_value={"results": [passage("a"), passage("b")], "error": None}), patch.object(retrieval, "keyword_search", return_value={"results": [], "error": None}), patch.object(retrieval, "rerank", return_value=(reordered, {"active": True})):
            result = retrieval.hybrid_search("HTTP 503")
        self.assertEqual(result["results"][0]["id"], "b")
        self.assertEqual(result["results"][0]["score_type"], "cross_encoder_logit")


if __name__ == "__main__":
    unittest.main()
