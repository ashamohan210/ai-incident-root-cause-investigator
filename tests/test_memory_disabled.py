"""Active architecture guarantees: no hosted memory, unchanged RAG validation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from streamlit.testing.v1 import AppTest
from src.incident_investigator.memory import (memory_enabled, platform_client, InvestigationMemory,
    MemoryUnavailable, Scope, UsageGuard)
from src.incident_investigator.investigation import investigate
from test_investigation import QUERY, model, retrieval


class DisabledMemoryTests(unittest.TestCase):
    def test_disabled_config_prevents_sdk_initialization_even_with_key(self):
        self.assertFalse(memory_enabled())
        sdk_module = MagicMock()
        with patch.dict(sys.modules, {'mem0': sdk_module}), patch.dict('os.environ', {'MEM0_API_KEY': 'dummy-test-placeholder'}), patch('httpx.Client.send') as send:
            with self.assertRaises(MemoryUnavailable): platform_client()
            with self.assertRaises(MemoryUnavailable): InvestigationMemory()
            sdk_module.MemoryClient.assert_not_called()
            send.assert_not_called()

    def test_adapter_and_transport_block_preexisting_clients(self):
        sdk = MagicMock()
        adapter = InvestigationMemory(sdk)
        scope = Scope('engineer', 'incident-A', 'session-1')
        with self.assertRaises(MemoryUnavailable): adapter.retrieve(scope)
        with self.assertRaises(MemoryUnavailable): adapter.add_fact(scope, 'user_fact', 'User detail')
        self.assertEqual(sdk.mock_calls, [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'usage.json'
            for method, endpoint in [('GET','/v1/ping/'), ('POST','/v3/memories/'), ('POST','/v3/memories/add/')]:
                with self.assertRaises(MemoryUnavailable): UsageGuard(path).before(httpx.Request(method, 'https://api.mem0.ai'+endpoint))
            self.assertFalse(path.exists())

    def test_scoped_legacy_caller_gets_memory_free_generation(self):
        memory = MagicMock()
        retriever = MagicMock(side_effect=retrieval)
        with patch('src.incident_investigator.memory.platform_client') as client, patch('httpx.Client.send') as send:
            result = investigate(QUERY, model(), retriever, Scope('user','incident','session'), memory)
            client.assert_not_called(); send.assert_not_called()
        self.assertEqual(memory.mock_calls, [])
        self.assertEqual(result['report']['status'], 'investigation')
        self.assertEqual(result['workflow_trace'], ['analyze','retrieve','check_evidence','generate','validate_citations'])
        self.assertNotIn('investigation_memory', result['report'])
        retriever.assert_called_once_with(QUERY)

    def test_session_user_context_used_for_followup_not_as_citations(self):
        llm = model(); retriever = MagicMock(side_effect=retrieval)
        context = ['HTTP 503 after deployment. We checked database connection pool limits.']
        result = investigate('What should we check next?', llm, retriever, session_context=context)
        self.assertEqual(result['report']['status'], 'investigation')
        self.assertIn(context[0], retriever.call_args.args[0])
        self.assertIn('CURRENT SESSION USER CONTEXT', llm.generate.call_args.args[0])
        self.assertIn(context[0], llm.generate.call_args.args[0])
        self.assertNotIn('save_memory', result['workflow_trace'])
        self.assertTrue(all(f['chunk_id']=='SYN-001:chunk:001' for f in result['report']['historical_root_causes']))
        with self.assertRaises(ValueError): investigate(QUERY, session_context=[{'role':'assistant','content':'invented cause'}])

    def test_full_streamlit_session_never_initializes_memory(self):
        real_investigate = investigate
        def run(description, **kwargs):
            return real_investigate(description, model(), retrieval, **kwargs)
        with patch('src.incident_investigator.ui.investigate', side_effect=run), patch('src.incident_investigator.memory.platform_client') as client, patch('httpx.Client.send') as send:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
            app.text_area[0].input(QUERY)
            next(b for b in app.button if b.label=='Run investigation').click().run()
            next(t for t in app.text_input if t.label=='Follow-up question').input('What should we check next?')
            next(b for b in app.button if b.label=='Send follow-up').click().run()
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state['workspaces'][app.session_state['active_investigation']]['turns']), 2)
            self.assertFalse(any('resume' in b.label.lower() for b in app.button))
            self.assertFalse(app.checkbox)
            self.assertTrue(any('current session' in row.value for row in app.info))
            client.assert_not_called(); send.assert_not_called()
