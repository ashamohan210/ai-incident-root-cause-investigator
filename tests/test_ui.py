"""Offline Streamlit interaction tests; no paid API calls or model generation."""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest
from src.incident_investigator.investigation import investigate
from src.incident_investigator.ui import DEMO_USER, display_text, public_url
from test_investigation import QUERY, model, retrieval


class UITests(unittest.TestCase):
    def setUp(self):
        self.result = investigate(QUERY, model(), retrieval)
        self.backend_patch = patch('src.incident_investigator.ui.investigate', return_value=self.result)
        self.backend = self.backend_patch.start()
        self.memory_patch = patch('src.incident_investigator.memory.InvestigationMemory')
        self.memory = self.memory_patch.start().return_value
        self.memory.retrieve.return_value = []
        self.memory.create_investigation.return_value = {'status': 'stored'}
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()

    def tearDown(self):
        self.backend_patch.stop(); self.memory_patch.stop()

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def run_incident(self):
        self.app.text_area[0].input(QUERY)
        self.button('Run investigation').click().run()
        self.assertFalse(self.app.exception)

    def test_home_no_api_calls_and_ids_survive_rerun(self):
        initial = self.app.session_state['active_investigation']
        session = self.app.session_state['ui_session_id']
        self.app.run()
        self.assertEqual(self.app.session_state['active_investigation'], initial)
        self.assertEqual(self.app.session_state['ui_session_id'], session)
        self.assertEqual(self.app.query_params['investigation'], initial)
        self.backend.assert_not_called(); self.memory.retrieve.assert_not_called()
        self.assertEqual(self.app.title[0].value, 'AI Incident Root Cause Investigator')

    def test_submission_citations_and_duplicate_guard(self):
        self.run_incident()
        kwargs = self.backend.call_args.kwargs
        self.assertNotIn('scope', kwargs)
        self.assertEqual(kwargs['session_context'], [])
        self.assertIn('SYN-001', '\n'.join(x.value for x in self.app.text))
        self.assertIn('unconfirmed', '\n'.join(x.value for x in self.app.subheader))
        self.button('Run investigation').click().run()
        self.assertEqual(self.backend.call_count, 1)
        self.app.run(); self.assertEqual(self.backend.call_count, 1)
        self.assertEqual(len(self.app.session_state['workspaces'][self.app.session_state['active_investigation']]['turns']), 1)

    def test_invalid_input_and_credentials_do_not_call_services(self):
        for text in ['', 'password=should-never-be-sent']:
            self.app.text_area[0].input(text)
            self.button('Run investigation').click().run()
            self.assertTrue(self.app.error)
        self.backend.assert_not_called(); self.memory.create_investigation.assert_not_called()

    def test_followup_uses_same_investigation_and_new_turn(self):
        self.run_incident()
        original = self.app.session_state['active_investigation']
        next(x for x in self.app.text_input if x.label == 'Follow-up question').input('What checks have we already performed?')
        self.button('Send follow-up').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state['active_investigation'], original)
        self.assertEqual(self.backend.call_args.kwargs['session_context'], [QUERY])
        self.assertEqual(self.backend.call_count, 2)
        self.memory.create_investigation.assert_not_called()
        self.assertEqual(len(self.app.session_state['workspaces'][original]['turns']), 2)

    def test_resume_is_explicit_and_switch_isolated(self):
        self.run_incident()
        first = self.app.session_state['active_investigation']
        self.app.text_input(key='session_investigation_id').input('other-investigation')
        self.button('Open session investigation').click().run()
        self.assertEqual(self.app.session_state['active_investigation'], 'other-investigation')
        self.assertFalse(self.app.session_state['workspaces']['other-investigation']['turns'])
        self.assertTrue(self.app.session_state['workspaces'][first]['turns'])
        self.memory.retrieve.assert_not_called()
        count = self.memory.retrieve.call_count; self.app.run()
        self.assertEqual(self.memory.retrieve.call_count, count)

    def test_bookmark_restores_id_with_new_session(self):
        old_session = self.app.session_state['ui_session_id']
        other = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')); other.query_params['investigation'] = 'bookmarked-incident'; other.run()
        self.assertFalse(other.exception)
        self.assertEqual(other.session_state['active_investigation'], 'bookmarked-incident')
        self.assertNotEqual(other.session_state['ui_session_id'], old_session)
        self.memory.retrieve.assert_not_called()

    def test_insufficient_evidence_and_missing_services(self):
        self.backend.return_value = investigate('Quantum helium decoherence', model(), lambda _: {'results': [], 'error': 'Pinecone unavailable'})
        self.run_incident()
        self.assertTrue(any('Insufficient' in x.value for x in self.app.warning))
        self.assertTrue(any('Pinecone' in x.value for x in self.app.warning))
        self.button('Open session investigation').click().run()
        self.assertFalse(self.app.exception)
        self.memory.retrieve.assert_not_called()

    def test_unexpected_failure_safe_and_not_retried(self):
        self.backend.side_effect = RuntimeError('secret internal stack detail')
        self.run_incident()
        self.assertTrue(self.app.error)
        self.assertNotIn('secret internal stack detail', str(self.app))
        self.assertFalse(self.app.session_state['busy'])
        self.button('Run investigation').click().run()
        self.assertEqual(self.backend.call_count, 1)

    def test_safe_links_and_plain_text(self):
        self.assertIsNone(public_url('javascript:alert(1)'))
        self.assertIsNone(public_url('file:///etc/passwd'))
        self.assertIsNone(public_url('https://user:password@example.com'))
        self.assertIsNone(public_url('https://example.com/?api_key=do-not-expose'))
        self.assertEqual(public_url('https://example.com/postmortem'), 'https://example.com/postmortem')
        with patch.dict('os.environ', {'DEMO_API_KEY': 'never-show-this-value'}):
            self.assertNotIn('never-show-this-value', display_text('source never-show-this-value'))
        # Document HTML is passed to st.text, never unsafe_allow_html.
        self.assertEqual(display_text('<script>alert(1)</script>'), '<script>alert(1)</script>')

    def test_public_source_link_and_synthetic_label(self):
        result = json.loads(json.dumps(self.result))
        result['report']['historical_root_causes'][0].update(source_type='public', source_url='https://example.com/postmortem')
        self.backend.return_value = result
        self.run_incident()
        self.assertTrue(any(link.url == 'https://example.com/postmortem' for link in self.app.get('link_button')))
        self.assertIn('Synthetic training example', '\n'.join(row.value for row in self.app.text))

    def test_ollama_failure_does_not_show_stack(self):
        self.backend.return_value = investigate(QUERY, model([TimeoutError()]), retrieval)
        self.run_incident()
        self.assertTrue(any('Ollama' in row.value for row in self.app.warning))

    def test_session_switch_restores_local_inputs_without_memory(self):
        original = self.app.session_state['active_investigation']
        next(row for row in self.app.text_input if row.label == 'Affected service').input('payment API')
        self.run_incident()
        self.app.text_input(key='session_investigation_id').input('other-investigation')
        self.button('Open session investigation').click().run()
        self.app.text_input(key='session_investigation_id').input(original)
        self.button('Open session investigation').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.text_area[0].value, QUERY)
        self.assertEqual(next(row for row in self.app.text_input if row.label == 'Affected service').value, 'payment API')
        self.memory.create_investigation.assert_not_called()
        self.memory.retrieve.assert_not_called()
