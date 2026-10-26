"""Offline regressions for budgets, public documents, and vector reuse."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.incident_investigator import embedding_store as store
from src.incident_investigator.ingestion import ROOT, IncidentJSONLoader, prepare


class PublicPipelineTests(unittest.TestCase):
    @unittest.skipUnless(any((ROOT / "data/incidents/public").glob("*.json")), "Requires independently obtained public report fixtures")
    def test_public_null_fields_and_source_metadata(self):
        path = next((ROOT / "data/incidents/public").glob("*.json"))
        document = IncidentJSONLoader(path).load()[0]
        self.assertEqual(document.metadata["source_type"], "public")
        self.assertTrue(document.metadata["source_url"].startswith("http"))
        self.assertIsNone(document.metadata["severity"])
        chunks, summary = prepare()
        self.assertFalse(summary["invalid_documents"])
        self.assertEqual(summary["synthetic_incidents"], 20)
        self.assertTrue(all("source_url" in c["metadata"] for c in chunks))

    def test_cache_reuses_only_matching_content_and_model(self):
        original = [json.loads(line) for line in (ROOT / "data/processed/chunks.jsonl").read_text().splitlines()][:2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/processed").mkdir(parents=True)
            source = root / "data/processed/chunks.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in original))
            provider = MagicMock()
            provider.availability.return_value = {"model": "embeddinggemma:300m", "model_digest": "digest1"}
            provider.embed_documents.side_effect = lambda texts: [[1.0] * 768 for _ in texts]
            with patch.object(store, "ROOT", root), patch.object(store, "OUT", root / "data/local_embeddings"), patch.object(store, "embedding_provider", return_value=provider):
                self.assertEqual(store.refresh()["newly_generated_embeddings"], 2)
                provider.embed_documents.reset_mock()
                self.assertEqual(store.refresh()["reused_embeddings"], 2)
                provider.embed_documents.assert_not_called()
                original[0]["page_content"] += "\n"
                source.write_text("".join(json.dumps(row) + "\n" for row in original))
                self.assertEqual(store.refresh()["newly_generated_embeddings"], 1)
                provider.availability.return_value["model_digest"] = "digest2"
                self.assertEqual(store.refresh()["newly_generated_embeddings"], 2)

    def test_collection_caps_and_repeat_run_guard(self):
        spec = importlib.util.spec_from_file_location("collector", ROOT / "scripts/collect_public_incidents.py")
        collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector)
        client = MagicMock()
        counter = iter(range(7))

        def search(**kwargs):
            n = next(counter)
            self.assertEqual(kwargs["search_depth"], "basic")
            self.assertFalse(kwargs["auto_parameters"])
            return {"usage": {"credits": 1}, "results": [
                {"url": f"https://github.blog/test/{n}-{j}", "title": "Incident outage"} for j in range(8)]}

        def extract(**kwargs):
            self.assertLessEqual(len(kwargs["urls"]), 5)
            self.assertEqual(kwargs["extract_depth"], "basic")
            return {"usage": {"credits": 1}, "results": []}

        client.search.side_effect = search
        client.extract.side_effect = extract
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, "OUT", Path(directory)), patch.object(collector, "TavilyClient", return_value=client), patch.object(collector, "load_dotenv"), patch.dict("os.environ", {"TAVILY_API_KEY": "offline-test"}), patch("sys.argv", ["collector", "--approved"]), patch("builtins.print"):
            collector.main()
            ledger = json.loads((Path(directory) / "usage.json").read_text())
            self.assertEqual(ledger["search_calls"], 7)
            self.assertEqual(ledger["extract_calls"], 6)
            self.assertEqual(ledger["reported_credits"], 13)
            with self.assertRaises(SystemExit):
                collector.main()
            self.assertEqual(client.search.call_count, 7)
            self.assertEqual(client.extract.call_count, 6)


if __name__ == "__main__":
    unittest.main()
