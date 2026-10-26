"""Offline evidence-viewer regressions with fictional temporary source records."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from src.incident_investigator.incident_viewer import load_incident, group_incidents, IncidentUnavailable
from src.incident_investigator.investigation import investigate
from test_investigation import QUERY, model, retrieval

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ID = 'PUB-0123456789ab'


class IncidentViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        for kind in ('synthetic', 'public'):
            (self.root/'data/incidents'/kind).mkdir(parents=True)
        self.synthetic = {'incident_id':'SYN-001','title':'Fictional Payments API source',
            'source_type':'synthetic','date':'2025-01-01','affected_service':'Payments API',
            'severity':'SEV-2','symptoms':'Fictional connection errors','error_codes':['HTTP 503'],
            'timeline':[{'time':'09:00','event':'Fictional detection'}],
            'root_cause':'Fictional pool limit defect','resolution':'Fictional controlled recovery',
            'preventive_actions':['Fictional capacity test'],
            'full_report':'FICTIONAL original narrative <script>unsafe()</script>'}
        self.public = {'incident_id':PUBLIC_ID,'title':'Fictional public-record fixture',
            'source_type':'public','publisher':'Example test publisher','incident_date':'2025-02-01',
            'source_url':'https://example.com/engineering/fixture','root_cause':None}
        self.write(self.synthetic); self.write(self.public)
        self.root_patch=patch('src.incident_investigator.incident_viewer.ROOT',self.root)
        self.root_patch.start()
        self.result=investigate(QUERY,model(),retrieval)
        self.backend_patch=patch('src.incident_investigator.ui.investigate',return_value=self.result)
        self.backend=self.backend_patch.start()

    def tearDown(self):
        self.backend_patch.stop();self.root_patch.stop();self.temp.cleanup()

    def write(self, record):
        p=self.root/'data/incidents'/record['source_type']/(record['incident_id']+'.json')
        p.write_text(json.dumps(record));return p

    def app(self):
        app=AppTest.from_file(str(ROOT/'app.py')).run()
        app.text_area[0].input(QUERY)
        next(b for b in app.button if b.label=='Run investigation').click().run()
        self.assertFalse(app.exception)
        return app

    def click(self, app, label, index=0):
        [b for b in app.button if b.label==label][index].click().run()
        self.assertFalse(app.exception)

    def text(self,app):
        return '\n'.join(x.value for x in app.text)

    def test_synthetic_opens_original_values_without_backend_calls(self):
        app=self.app();self.assertEqual(self.backend.call_count,1)
        self.click(app,'View full incident report')
        text=self.text(app)
        for value in ['Fictional Payments API source','2025-01-01','SEV-2',
                      'Fictional pool limit defect','Fictional controlled recovery',
                      'Fictional capacity test','<script>unsafe()</script>']:
            self.assertIn(value,text)
        self.assertTrue(any('Fictional synthetic example' in x.value for x in app.info))
        self.assertEqual(self.backend.call_count,1)
        self.click(app,'Close full incident report')
        self.assertNotIn('FICTIONAL original narrative',self.text(app))
        self.assertEqual(self.backend.call_count,1)

    def test_public_partial_record_uses_original_link_and_missing_labels(self):
        row={**self.result['report']['historical_root_causes'][0],
             'incident_id':PUBLIC_ID,'source_type':'public','title':self.public['title'],
             'source_url':self.public['source_url'],'chunk_id':PUBLIC_ID+':chunk:001'}
        self.result['report'].update(similar_historical_incidents=[row],historical_root_causes=[],
            previous_resolutions=[],historical_observations=[row])
        app=self.app();self.click(app,'View full incident report')
        links=[x for x in app.get('link_button') if x.label=='View original postmortem']
        self.assertEqual(links[0].url,self.public['source_url'])
        self.assertIn(self.public['publisher'],self.text(app))
        self.assertIn(self.public['incident_date'],self.text(app))
        self.assertIn('Not recorded in this source record.',self.text(app))
        self.assertTrue(any('No full narrative' in x.value for x in app.info))
        self.assertEqual(self.backend.call_count,1)

    def test_causes_resolutions_grouped_and_passage_ids_visible(self):
        before=copy.deepcopy(self.result['report'])
        groups=group_incidents(before)
        self.assertEqual(len(groups),1)
        self.assertEqual({heading for heading,row in groups[0]['findings']},
                         {'Historical root causes','Documented historical resolutions'})
        self.assertEqual(before,self.result['report'])
        app=self.app()
        self.assertEqual(len([b for b in app.button if b.label=='View full incident report']),1)
        captions='\n'.join(x.value for x in app.caption)
        self.assertIn('SYN-001:chunk:001',captions)
        self.assertIn('Database connection pool exceeded capacity.',self.text(app))
        self.assertIn('Restore safe pool limits.',self.text(app))

    def test_missing_and_corrupt_sources_are_friendly(self):
        path=self.root/'data/incidents/synthetic/SYN-001.json';path.unlink()
        app=self.app();self.click(app,'View full incident report')
        self.assertTrue(any('not available' in x.value for x in app.info))
        self.assertIn('Restore safe pool limits.',self.text(app))
        path.write_text('{broken')
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('unreadable or invalid' in x.value for x in app.info))
        self.assertEqual(self.backend.call_count,1)

    def test_session_report_preserved_and_multiple_cards_independent(self):
        second={**self.synthetic,'incident_id':'SYN-002','title':'Second fictional incident'};self.write(second)
        self.result['report']['similar_historical_incidents'].append({
            'incident_id':'SYN-002','title':second['title'],'source_type':'synthetic',
            'source_reference':'data/incidents/synthetic/SYN-002.json','chunk_id':'SYN-002:chunk:001'})
        app=self.app();identifier=app.session_state['active_investigation']
        before=copy.deepcopy(app.session_state['workspaces'][identifier]['turns'])
        self.assertEqual(len([b for b in app.button if b.label=='View full incident report']),2)
        self.click(app,'View full incident report',1)
        self.assertIn(second['title'],self.text(app))
        self.assertNotIn('Fictional Payments API source',self.text(app))
        self.click(app,'View full incident report')
        self.assertIn('Fictional Payments API source',self.text(app))
        self.assertEqual(len([b for b in app.button if b.label=='Close full incident report']),2)
        self.assertEqual(before,app.session_state['workspaces'][identifier]['turns'])
        self.assertEqual(self.backend.call_count,1)

    def test_paths_symlinks_and_identity_mismatches_rejected(self):
        for identifier,kind in [('../../.env','synthetic'),('SYN-001','../../'),('bad','public')]:
            with self.assertRaises(IncidentUnavailable):load_incident(identifier,kind)
        # Even a source-looking JSON symlink cannot expose another local file.
        external=self.root/'unrelated.json';external.write_text(json.dumps(self.synthetic))
        path=self.root/'data/incidents/synthetic/SYN-001.json';path.unlink();path.symlink_to(external)
        with self.assertRaises(IncidentUnavailable):load_incident('SYN-001','synthetic')
        path.unlink();self.write({**self.synthetic,'incident_id':'SYN-002'})
        path.write_text(json.dumps({**self.synthetic,'incident_id':'SYN-999'}))
        with self.assertRaises(IncidentUnavailable):load_incident('SYN-001','synthetic')

    def test_untrusted_citation_path_ignored(self):
        self.result['report']['similar_historical_incidents'][0]['source_reference']='../../.env'
        app=self.app();self.click(app,'View full incident report')
        self.assertIn('Fictional Payments API source',self.text(app))
        self.assertEqual(load_incident('SYN-001','synthetic'),self.synthetic)

    def test_invalid_public_url_not_clickable(self):
        self.public['source_url']='javascript:alert(1)';self.write(self.public)
        row={'incident_id':PUBLIC_ID,'title':self.public['title'],'source_type':'public'}
        self.result['report'].update(similar_historical_incidents=[row],historical_root_causes=[],previous_resolutions=[])
        app=self.app();self.click(app,'View full incident report')
        self.assertFalse(list(app.get('link_button')))

    def test_fallback_does_not_offer_unvalidated_cards(self):
        self.result['report']['status']='insufficient_evidence'
        self.assertEqual(group_incidents(self.result['report']),[])
        app=self.app()
        self.assertFalse([b for b in app.button if b.label=='View full incident report'])

    def test_dataset_directory_symlinks_are_rejected(self):
        folder=self.root/'data/incidents/synthetic'
        moved=self.root/'moved-dataset';folder.rename(moved);folder.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(IncidentUnavailable):load_incident('SYN-001','synthetic')

    def test_public_source_unavailable_still_offers_validated_url(self):
        row={'incident_id':'PUB-111111111111','title':'Missing fictional public fixture',
             'source_type':'public','source_url':'https://example.com/verified-citation'}
        self.result['report'].update(similar_historical_incidents=[row],historical_root_causes=[],previous_resolutions=[])
        app=self.app();self.click(app,'View full incident report')
        self.assertTrue(any('not available' in x.value for x in app.info))
        self.assertTrue(any(x.label=='View original postmortem' and x.url==row['source_url'] for x in app.get('link_button')))
        self.assertEqual(self.backend.call_count,1)
