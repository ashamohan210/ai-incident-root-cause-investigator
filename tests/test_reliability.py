"""Phase 9 offline reliability regressions; no Ollama or external service calls."""
import copy
import json
import unittest
from unittest.mock import patch
from src.incident_investigator.evidence_catalog import (build_catalog,validate_catalog,ReportSelection,
    resolve_selection,render_hypothesis,validate_mechanisms)
from src.incident_investigator.investigation import investigate,Hypothesis,Quote,validate_quotes
from test_investigation import PASSAGE,QUERY,DECISION,DRAFT,model,retrieval

DNS={**PASSAGE,'id':'public-dns:chunk:002','source_type':'public','incident_id':'public-dns',
     'chunk_text':'FICTIONAL FIXTURE: Two lab DNS nodes accepted new settings. A rollout defect restarted the authoritative node but left the cache node running stale settings. Restarting both lab nodes restored lookups.'}


class ReliabilityTests(unittest.TestCase):
    def test_resolution_recovered_before_alignment(self):
        result=investigate(QUERY,model([json.dumps(DECISION),json.dumps({'finding_ids':['F001'],'hypothesis_fact_ids':['F001']})]),retrieval)
        self.assertEqual(result['report']['status'],'investigation')
        self.assertEqual(result['report']['previous_resolutions'][0]['supporting_passage'],'Restore safe pool limits.')

    def test_hypothesis_must_already_be_selected_cause(self):
        catalog=build_catalog([PASSAGE])
        for selection in [ReportSelection(finding_ids=['F002'],hypothesis_fact_ids=['F001']),ReportSelection(finding_ids=['F002'],hypothesis_fact_ids=['F002'])]:
            self.assertTrue(resolve_selection(selection,catalog,[PASSAGE])[2])

    def test_unknown_ids_rejected_without_silent_dropping(self):
        result=investigate(QUERY,model([json.dumps(DECISION),json.dumps({'finding_ids':['F001','FAKE'],'hypothesis_fact_ids':[]})]),retrieval)
        self.assertEqual(result['report']['status'],'insufficient_evidence')
        self.assertEqual(result['report']['historical_root_causes'],[])

    def test_invented_quote_rejected_at_schema_and_source_layers(self):
        extra={**DRAFT,'quote':'An invented quotation.'}
        self.assertEqual(investigate(QUERY,model([json.dumps(DECISION),json.dumps(extra)]),retrieval)['report']['status'],'insufficient_evidence')
        catalog=build_catalog([PASSAGE]);catalog[0]['quote']='An invented quotation.'
        self.assertTrue(validate_catalog(catalog,[PASSAGE]))
        self.assertTrue(validate_quotes([Quote(chunk_id=PASSAGE['id'],quote='invented')],[PASSAGE]))

    def test_reversed_dns_actor_is_rejected(self):
        trusted={**DNS,'source_type':'synthetic','chunk_text':'root_cause: FICTIONAL FIXTURE: The authoritative node restarted; the cache node missed its required restart.\nDNS name server configuration bug.'}
        catalog=build_catalog([trusted]);cause=next(f for f in catalog if f['kind']=='root_cause')
        valid=Hypothesis(**render_hypothesis(cause))
        self.assertEqual(validate_mechanisms([valid],[cause]),[])
        reversed_claim=valid.model_copy(update={'hypothesis':'The authoritative name server did not restart.'})
        self.assertTrue(validate_mechanisms([reversed_claim],[cause]))
        result=investigate('DNS name server configuration bug',model([json.dumps({'sufficient':True,'supporting_fact_ids':[cause['fact_id']]}),json.dumps({'finding_ids':[cause['fact_id']],'hypothesis_fact_ids':[cause['fact_id']]})]),lambda _: {'results':[trusted]})
        text=result['report']['current_incident_hypotheses'][0]['hypothesis']
        self.assertIn('the cache node missed its required restart',text)
        self.assertNotIn('did not restart',text)

    def test_labeling_resolution_as_root_cause_rejected(self):
        for source in [PASSAGE]:
            catalog=build_catalog([source]);fact=next(f for f in catalog if f['kind']=='resolution');fact['kind']='root_cause'
            self.assertTrue(validate_catalog(catalog,[source]))

    def test_negated_public_cause_is_not_promoted(self):
        row={**DNS,'chunk_text':'The database was not the cause because its connections remained healthy throughout the outage.'}
        self.assertTrue(all(f['kind']=='observation' for f in build_catalog([row])))

    def test_missing_evidence_never_generates(self):
        llm=model();r=investigate(QUERY,llm,lambda _: {'results':[]})
        self.assertEqual(r['report']['status'],'insufficient_evidence');llm.generate.assert_not_called()

    def test_malformed_and_unsupported_prose_selections_fail_closed(self):
        for invalid in ['not json','{}',json.dumps({**DRAFT,'hypothesis':'The current root cause is proven.'}),json.dumps({'finding_ids':[],'hypothesis_fact_ids':[]})]:
            result=investigate(QUERY,model([json.dumps(DECISION),invalid]),retrieval)
            self.assertEqual(result['report']['status'],'insufficient_evidence')

    def test_factual_answer_need_not_invent_current_hypothesis(self):
        result=investigate(QUERY,model([json.dumps(DECISION),json.dumps({'finding_ids':['F001'],'hypothesis_fact_ids':[]})]),retrieval)
        self.assertEqual(result['report']['status'],'investigation')
        self.assertEqual(result['report']['current_incident_hypotheses'],[])

    def test_schema_exposes_actual_catalog_ids_only(self):
        llm=model();investigate(QUERY,llm,retrieval)
        schema=llm.generate.call_args.args[1]
        self.assertEqual(schema['properties']['finding_ids']['items']['enum'],['F001','F002'])
        self.assertEqual(schema['properties']['hypothesis_fact_ids']['items']['enum'],['F001'])

    def test_offsets_checked_even_when_quote_occurs_elsewhere(self):
        catalog=build_catalog([PASSAGE]);catalog[0]['start']+=1
        self.assertTrue(validate_catalog(catalog,[PASSAGE]))

    def test_public_prevention_and_background_remain_observations(self):
        row={**DNS,'chunk_text':'Short-term remediations improve resilience to any loss of service caused by dependencies. A previous syncing architecture caused consistency problems that migration should prevent.'}
        catalog=build_catalog([row])
        self.assertTrue(catalog)
        self.assertTrue(all(f['kind']=='observation' for f in catalog))
        catalog[0]['kind']='root_cause'
        self.assertTrue(validate_catalog(catalog,[row]))

    def test_source_title_cannot_be_reassigned(self):
        catalog=build_catalog([PASSAGE]);catalog[0]['title']='An unrelated service'
        self.assertTrue(validate_catalog(catalog,[PASSAGE]))
