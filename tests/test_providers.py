"""Offline checks of provider configuration and embedding response safety."""
import unittest
from unittest.mock import patch

from src.incident_investigator.providers import (
    OllamaEmbeddings, ProviderError, embedding_provider, settings, validate_vectors,
)


class ProviderTests(unittest.TestCase):
    def test_defaults_and_override(self):
        with patch.dict("os.environ", {"EMBEDDING_PROVIDER": "ollama", "LLM_PROVIDER": "ollama"}):
            self.assertEqual(settings()["embedding_provider"], "ollama")
            self.assertEqual(settings()["memory_provider"], "disabled")
        with patch.dict("os.environ", {"EMBEDDING_PROVIDER": "nebius"}):
            with self.assertRaises(ProviderError):
                embedding_provider()

    def test_invalid_vectors(self):
        for vectors in [[], [[0, 0]], [[float("nan")]], [[float("inf")]], [[True]], [[1], [1, 2]]]:
            with self.subTest(vectors=vectors), self.assertRaises(ProviderError):
                validate_vectors(vectors, len(vectors))
        self.assertEqual(validate_vectors([[1.0, 0.5]], 1), 2)

    def test_task_format_and_no_truncation(self):
        provider = OllamaEmbeddings("embeddinggemma:300m", "http://127.0.0.1:11434")
        with patch.object(provider, "request", return_value={"embeddings": [[1.0, 0.5]]}) as request:
            provider.embed_documents(["incident"])
            body = request.call_args.args[1]
            self.assertEqual(body["input"], ["title: none | text: incident"])
            self.assertFalse(body["truncate"])
            provider.embed_query("503 errors")
            self.assertEqual(request.call_args.args[1]["input"], ["task: search result | query: 503 errors"])

    def test_remote_endpoint_rejected(self):
        with self.assertRaises(ProviderError):
            OllamaEmbeddings("embeddinggemma:300m", "https://example.com")

    def test_empty_inputs_rejected(self):
        provider = OllamaEmbeddings("embeddinggemma:300m", "http://127.0.0.1:11434")
        with self.assertRaises(ProviderError):
            provider.embed_query(" ")
        with self.assertRaises(ProviderError):
            provider.embed_documents([""])


if __name__ == "__main__":
    unittest.main()
