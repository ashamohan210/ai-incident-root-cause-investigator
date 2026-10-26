"""Workflow behavior regressions with fake local LLM/retrieval, not RAG evaluation."""
import json
import unittest
from unittest.mock import MagicMock, patch

from src.incident_investigator.investigation import investigate, EvidenceDecision, Draft, cautious_hypothesis
from src.incident_investigator.providers import OllamaLLM, ProviderError, settings

PASSAGE = {"id": "SYN-001:chunk:001", "incident_id": "SYN-001", "title": "Payments API",
           "source_type": "synthetic", "source": "data/incidents/synthetic/SYN-001.json", "source_url": None,
           "chunk_text": "root_cause: Database connection pool exceeded capacity.\nresolution: Restore safe pool limits.\nHTTP 503 after deployment. Database connection pool exceeded capacity. Restore safe pool limits."}
QUERY = "Investigate HTTP 503 after deployment with high database connections"
DECISION = {"sufficient": True, "supporting_fact_ids": ["F001"]}
DRAFT = {"finding_ids": ["F001", "F002"], "hypothesis_fact_ids": ["F001"]}


def model(responses=None):
    instance = MagicMock()
    instance.generate.side_effect = responses or [json.dumps(DECISION), json.dumps(DRAFT)]
    instance.last_metrics = {"wall_seconds": 0.1}
    return instance


def retrieval(query):
    return {"results": [PASSAGE], "error": None, "warnings": []}


class InvestigationTests(unittest.TestCase):
    def test_graph_executes_and_reuses_retrieval(self):
        retriever = MagicMock(side_effect=retrieval)
        result = investigate(QUERY, model(), retriever)
        retriever.assert_called_once_with(QUERY)
        self.assertEqual(result["workflow_trace"], ["analyze", "retrieve", "check_evidence", "generate", "validate_citations"])
        report = result["report"]
        self.assertEqual(report["status"], "investigation")
        self.assertFalse(report["current_root_cause_confirmed"])
        self.assertEqual(report["historical_root_causes"][0]["incident_id"], "SYN-001")
        self.assertEqual(report["historical_root_causes"][0]["reference"], PASSAGE["source"])

    def test_empty_retrieval_never_calls_llm(self):
        llm = model()
        result = investigate(QUERY, llm, lambda _: {"results": [], "error": None})
        self.assertEqual(result["report"]["status"], "insufficient_evidence")
        llm.generate.assert_not_called()
        self.assertIn("validate_citations", result["workflow_trace"])

    def test_declarative_hypothesis_is_presented_as_unconfirmed(self):
        text = cautious_hypothesis("The current incident's root cause is exhausted connections.")
        self.assertNotIn("root cause is", text)
        self.assertIn("not established", text)

    def test_omitted_synthetic_resolution_is_recovered_verbatim(self):
        draft = json.loads(json.dumps(DRAFT))
        draft["finding_ids"] = ["F001"]
        passage = {**PASSAGE, "chunk_text": PASSAGE["chunk_text"] + "\nresolution: Restore safe pool limits."}
        result = investigate(QUERY, model([json.dumps(DECISION), json.dumps(draft)]),
                             lambda _: {"results": [passage], "error": None})
        resolution = result["report"]["previous_resolutions"][0]
        self.assertEqual(resolution["supporting_passage"], "Restore safe pool limits.")
        self.assertIn(resolution["supporting_passage"], passage["chunk_text"])
        self.assertIn("retrieval_seconds", result["timings"])

    def test_saved_report_audit_rejects_unsupported_history(self):
        from scripts.verify_phase6 import audit
        result = investigate(QUERY, model(), retrieval)
        self.assertTrue(audit(result)["passed"])
        result["report"]["historical_root_causes"][0]["supporting_passage"] = "Invented finding"
        self.assertFalse(audit(result)["passed"])

    def test_unknown_topic_rejects_nearest_neighbors(self):
        llm = model()
        result = investigate("Quantum processor decoherence following helium purge", llm, retrieval)
        self.assertEqual(result["report"]["current_incident_hypotheses"], [])
        llm.generate.assert_not_called()

    def test_llm_evidence_insufficient(self):
        llm = model([json.dumps({"sufficient": False, "supporting_fact_ids": []})])
        self.assertEqual(investigate(QUERY, llm, retrieval)["report"]["status"], "insufficient_evidence")
        self.assertEqual(llm.generate.call_count, 1)

    def test_unretrieved_citation_and_invented_quote_rejected(self):
        for draft in [
            {"finding_ids": ["SYN-999:chunk:001"], "hypothesis_fact_ids": []},
            {"finding_ids": ["F001"], "hypothesis_fact_ids": [], "quote": "An invented cause."},
        ]:
            result = investigate(QUERY, model([json.dumps(DECISION), json.dumps(draft)]), retrieval)
            self.assertEqual(result["report"]["status"], "insufficient_evidence")
            self.assertTrue(result["report"]["citation_validation_issues"])

    def test_parsing_failure_and_timeout_are_safe(self):
        for responses in [["not JSON"], [TimeoutError()], [json.dumps(DECISION), "{}"], [json.dumps(DECISION), TimeoutError()]]:
            result = investigate(QUERY, model(responses), retrieval)
            self.assertEqual(result["report"]["status"], "insufficient_evidence")
            self.assertFalse(result["report"]["current_root_cause_confirmed"])

    def test_invalid_evidence_gate_citation_is_rejected(self):
        decision = {"sufficient": True, "supporting_fact_ids": ["SYN-999:chunk:001"]}
        llm = model([json.dumps(decision)])
        result = investigate(QUERY, llm, retrieval)
        self.assertEqual(result["report"]["status"], "insufficient_evidence")
        self.assertEqual(llm.generate.call_count, 1)

    def test_hypothesis_requires_validated_source_and_no_certainty(self):
        for changes in [{"hypothesis_fact_ids": ["SYN-999:chunk:001"]}, {"hypothesis": "The current cause is confirmed."}, {"hypothesis_fact_ids": ["F002"]}]:
            draft = {**DRAFT, **changes}
            result = investigate(QUERY, model([json.dumps(DECISION), json.dumps(draft)]), retrieval)
            self.assertEqual(result["report"]["status"], "insufficient_evidence")

    def test_retrieval_api_failure_and_invalid_input(self):
        result = investigate(QUERY, model(), lambda _: {"results": [], "error": "Unavailable"})
        self.assertTrue(result["report"]["retrieval_warnings"])
        with self.assertRaises(ValueError): investigate(" ", model(), retrieval)

    def test_generation_uses_bounded_local_options(self):
        llm = OllamaLLM(settings())
        response = {"done": True, "done_reason": "stop", "message": {"content": '{"ready":true}'}}
        with patch.object(llm.transport, "availability"), patch.object(llm.transport, "request", return_value=response) as request:
            llm.generate("Read provided evidence.", EvidenceDecision.model_json_schema())
        payload = request.call_args.args[1]
        self.assertEqual(payload["model"], "qwen3.5:4b")
        self.assertEqual(payload["options"]["num_ctx"], 8192)
        self.assertFalse(payload["think"])
        self.assertNotIn("format", payload)
        self.assertIn("JSON schema", payload["messages"][1]["content"])
        response["done_reason"] = "length"
        with patch.object(llm.transport, "availability"), patch.object(llm.transport, "request", return_value=response):
            with self.assertRaises(ProviderError): llm.generate("Evidence")
