"""Offline SDK-shaped tests: no external resources or network operations."""
import unittest
from unittest.mock import MagicMock, patch

from pinecone import FetchDocumentsResponse, SearchDocumentsResponse
from src.incident_investigator import pinecone_store as store
from src.incident_investigator.providers import ProviderError


class PineconeStoreTests(unittest.TestCase):
    @unittest.skipUnless((store.ROOT / "data/local_embeddings/embeddings.jsonl").exists(), "Requires original cached embedding snapshot; no live API is called")
    def test_local_payload(self):
        records, _, metrics = store.local_records()
        self.assertEqual(len(records), 104)
        self.assertLess(metrics["maximum_metadata_bytes"], 40000)
        self.assertEqual(len({r["_id"] for r in records}), 104)
        self.assertTrue(all(len(r["embedding"]) == 768 and r["chunk_text"] and r["source"] for r in records))
        self.assertTrue(all(None not in r.values() for r in records))

    def test_writes_need_approval_before_connecting(self):
        with patch.object(store, "client") as client:
            for action in (store.create_index, store.upload):
                with self.assertRaises(ProviderError):
                    action()
            client.assert_not_called()

    @unittest.skipUnless((store.ROOT / "data/local_embeddings/embeddings.jsonl").exists(), "Requires original cached embedding snapshot; no live API is called")
    def test_incompatible_schema_and_identity_rejected(self):
        _, manifest, _ = store.local_records()
        description = MagicMock()
        data = {"schema": store.proposed_schema(),
                "status": {"ready": True}, "tags": store.expected_tags(manifest)}
        description.to_dict.return_value = data
        store.compatible(description, manifest)
        data["schema"]["fields"]["embedding"]["dimension"] = 1024
        with self.assertRaises(ProviderError): store.compatible(description, manifest)
        data["schema"]["fields"]["embedding"]["dimension"] = 768
        data["tags"] = {}
        with self.assertRaises(ProviderError): store.compatible(description, manifest)
        data["tags"] = store.expected_tags(manifest)
        del data["schema"]["fields"]["chunk_text"]
        with self.assertRaises(ProviderError): store.compatible(description, manifest)

    def test_schema_supports_dense_and_text_without_metadata_declarations(self):
        fields = store.proposed_schema()["fields"]
        self.assertEqual(set(fields), {"embedding", "chunk_text"})
        self.assertEqual(fields["embedding"]["dimension"], 768)
        self.assertEqual(fields["embedding"]["metric"], "cosine")
        self.assertEqual(fields["chunk_text"]["type"], "string")
        self.assertIn("full_text_search", fields["chunk_text"])

    @unittest.skipUnless((store.ROOT / "data/local_embeddings/embeddings.jsonl").exists(), "Requires original cached embedding snapshot; no live API is called")
    def test_upload_and_fetch_use_documents_interface(self):
        records, _, _ = store.local_records()
        index = MagicMock()
        index.describe_index_stats.return_value.to_dict.return_value = {"namespaces": {"historical-incidents": {"vector_count": 104}}}

        def fetch(**kwargs):
            selected = {r["_id"]: r for r in records if r["_id"] in kwargs["ids"]}
            return FetchDocumentsResponse.from_dict({"documents": selected, "namespace": "historical-incidents"})

        index.documents.fetch.side_effect = fetch
        with patch.object(store, "open_index", return_value=index):
            self.assertEqual(store.upload(approved=True)["submitted"], 104)
            self.assertEqual(index.documents.upsert.call_count, 6)
            self.assertTrue(store.verify_remote()["passed"])
        index.upsert.assert_not_called()

    @unittest.skipUnless((store.ROOT / "data/local_embeddings/embeddings.jsonl").exists(), "Requires original cached embedding snapshot; no live API is called")
    def test_search_result_empty_and_error(self):
        records, manifest, _ = store.local_records()
        provider = MagicMock()
        provider.availability.return_value = {"model": manifest["model"], "model_digest": manifest["model_digest"]}
        provider.embed_query.return_value = [1.0] * 768
        index = MagicMock()
        hit = {k: v for k, v in records[0].items() if k != "embedding"}
        hit["_score"] = 0.9
        index.documents.search.return_value = SearchDocumentsResponse.from_dict({"matches": [hit]})
        with patch.object(store, "embedding_provider", return_value=provider), patch.object(store, "open_index", return_value=index):
            result = store.semantic_search("503 after deployment")
            self.assertIsNone(result["error"])
            self.assertEqual(result["results"][0]["incident_id"], hit["incident_id"])
            self.assertEqual(index.documents.search.call_args.kwargs["top_k"], 5)
            index.documents.search.return_value = SearchDocumentsResponse.from_dict({"matches": []})
            self.assertEqual(store.semantic_search("timeout")["results"], [])
            index.documents.search.side_effect = RuntimeError("sensitive raw error")
            self.assertNotIn("sensitive raw error", store.semantic_search("timeout")["error"])


if __name__ == "__main__":
    unittest.main()
