"""Hosted adapter behavior tested without remote API calls or local memory DB."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.incident_investigator.memory import Scope, InvestigationMemory, MemoryUnavailable, UsageGuard, confirmed_facts
from src.incident_investigator.investigation import investigate


class FakeSDK:
    def __init__(self, storage=None):
        self.storage = storage if storage is not None else []
        self.writes = 0

    def get_all(self, filters, **kwargs):
        return {"results": copy.deepcopy([r for r in self.storage if r["user_id"] == filters["user_id"]]), "next": None}

    def add(self, messages, user_id, metadata, infer):
        assert infer is False
        self.writes += 1
        identifier = f"memory-{len(self.storage) + 1}"
        self.storage.append({"id": identifier, "memory": messages[0]["content"], "metadata": metadata, "user_id": user_id})
        return {"results": [{"id": identifier, "event": "ADD"}]}


class MemoryTests(unittest.TestCase):
    def setUp(self):
        from src.incident_investigator.memory import memory_config
        config = {**memory_config(), "enabled": True}
        configured = patch('src.incident_investigator.memory.memory_config', return_value=config)
        configured.start()
        self.addCleanup(configured.stop)
        self.scope = Scope("engineer", "incident-A", "session-1")
        self.sdk = FakeSDK()
        self.memory = InvestigationMemory(self.sdk)

    def test_creation_persistence_across_sessions_and_duplicate_skip(self):
        self.memory.create_investigation(self.scope, "HTTP 503 for payment API")
        self.memory.add_fact(self.scope, "completed_check", "We checked the database connection pool.")
        second = InvestigationMemory(FakeSDK(self.sdk.storage))
        rows = second.retrieve(Scope("engineer", "incident-A", "session-2"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(any("connection pool" in r["memory"] for r in rows))
        self.assertEqual(self.memory.add_fact(self.scope, "completed_check", "We checked the database connection pool.")["status"], "duplicate_skipped")
        self.assertEqual(self.sdk.writes, 2)

    def test_isolation_by_both_user_and_investigation(self):
        self.memory.create_investigation(self.scope, "Private incident A")
        self.assertEqual(self.memory.retrieve(Scope("engineer", "incident-B", "session-1")), [])
        self.assertEqual(self.memory.retrieve(Scope("another-engineer", "incident-A", "session-1")), [])

    def test_wrong_scope_from_server_is_rejected(self):
        self.memory.create_investigation(self.scope, "Incident A")
        malicious = MagicMock()
        malicious.get_all.return_value = {"results": self.sdk.storage}
        with self.assertRaises(MemoryUnavailable):
            InvestigationMemory(malicious).retrieve(Scope("engineer", "incident-B", "session-2"))

    def test_supersession_preserves_old_remote_record(self):
        self.memory.add_fact(self.scope, "affected_service", "Payment API", fact_key="service")
        identifier = self.memory.retrieve(self.scope)[0]["id"]
        self.memory.supersede(self.scope, identifier, "Checkout API")
        rows = self.memory.retrieve(self.scope)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["memory"], "Checkout API")
        self.assertEqual(len(self.sdk.storage), 2)
        with self.assertRaises(ValueError):
            self.memory.supersede(Scope("engineer", "incident-B", "session-1"), identifier, "Other")

    def test_credentials_ai_hypotheses_and_deletion_blocked(self):
        with self.assertRaises(ValueError): self.memory.add_fact(self.scope, "ai_hypothesis", "Pool issue")
        with self.assertRaises(ValueError): self.memory.add_fact(self.scope, "user_fact", "API_KEY=do-not-store")
        with self.assertRaises(MemoryUnavailable): self.memory.clear_investigation(self.scope)
        with self.assertRaises(MemoryUnavailable): self.memory.clear_investigation(self.scope, approved=True)

    def test_http_limits_and_delete_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = UsageGuard(Path(directory) / "usage.json")
            request = httpx.Request("POST", "https://api.mem0.ai/v3/memories/add/", json={})
            for _ in range(8): guard.before(request)
            with self.assertRaises(MemoryUnavailable): guard.before(request)
            for _ in range(30): guard.before(httpx.Request("POST", "https://api.mem0.ai/v3/memories/", json={"filters": {"user_id": "rca_scoped"}}))
            with self.assertRaises(MemoryUnavailable): guard.before(httpx.Request("POST", "https://api.mem0.ai/v3/memories/", json={"filters": {"user_id": "rca_scoped"}}))
            with self.assertRaises(MemoryUnavailable): guard.before(httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/x/"))

    def test_conservative_extraction(self):
        facts = confirmed_facts("Investigate HTTP 503. We checked the database pool. We confirmed that database connection exhaustion is not the cause.")
        self.assertEqual([f["kind"] for f in facts], ["completed_check", "ruled_out"])
        self.assertEqual(confirmed_facts("Maybe the database pool is the cause?"), [])

    def test_graph_recall_and_new_fact_saving(self):
        self.memory.create_investigation(self.scope, "HTTP 503 payment API")
        llm = MagicMock()
        result = investigate("We checked the database connection pool.", llm, lambda _: {"results": [], "error": None}, self.scope, self.memory)
        self.assertIn("save_memory", result["workflow_trace"])
        second = Scope("engineer", "incident-A", "session-2")
        recall = investigate("What checks have we already performed?", llm, lambda _: {"results": [], "error": None}, second, self.memory)
        self.assertEqual(recall["report"]["status"], "memory_recall")
        self.assertIn("connection pool", recall["report"]["completed_checks"][0]["text"])
        llm.generate.assert_not_called()

    def test_graph_api_failure_does_not_crash(self):
        broken = MagicMock(); broken.retrieve.side_effect = RuntimeError("credential-like internal error")
        result = investigate("HTTP 503", MagicMock(), lambda _: {"results": [], "error": None}, self.scope, broken)
        self.assertTrue(result["report"]["investigation_memory"]["warnings"])
        self.assertNotIn("credential-like", json.dumps(result))

    def test_async_write_is_not_claimed_as_persisted(self):
        sdk = MagicMock()
        sdk.get_all.return_value = {"results": [], "next": None}
        sdk.add.return_value = {"status": "PENDING", "event_id": "test-event"}
        result = InvestigationMemory(sdk).create_investigation(self.scope, "HTTP 503")
        self.assertEqual(result["status"], "queued")
        sdk.add.assert_called_once()

    def test_mem0_ids_cannot_be_historical_citations(self):
        self.memory.create_investigation(self.scope, "HTTP 503 after deployment")
        source = {"id": "SYN-005:chunk:001", "incident_id": "SYN-005", "title": "Gateway",
                  "source_type": "synthetic", "source": "source.json", "source_url": None,
                  "chunk_text": "root_cause: Readiness probes admitted traffic too early.\nHTTP 503 after deployment. Readiness probes admitted traffic too early."}
        llm = MagicMock(); llm.last_metrics = {}
        llm.generate.side_effect = [json.dumps({"sufficient": True, "supporting_fact_ids": ["F001"]}),
            json.dumps({"finding_ids": ["memory-1"], "hypothesis_fact_ids": ["memory-1"]})]
        result = investigate("HTTP 503 after deployment", llm, lambda _: {"results": [source], "error": None}, self.scope, self.memory)
        self.assertEqual(result["report"]["status"], "insufficient_evidence")
        self.assertTrue(result["report"]["citation_validation_issues"])
