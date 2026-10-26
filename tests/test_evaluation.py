"""Offline checks of labels and metric arithmetic, not invented RAG scores."""
import unittest
from pathlib import Path
from src.incident_investigator.evaluation import load_dataset,retrieval_metrics,aggregate
ROOT=Path(__file__).resolve().parents[1]

class EvaluationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "evaluation/questions.json").exists() and (ROOT / "data/processed/chunks.jsonl").exists(), "Requires original evaluated dataset and full local corpus; publication inventory is not a substitute")
    def test_frozen_dataset_distribution_and_verbatim_references(self):
        dataset,chunks=load_dataset(ROOT/'evaluation/questions.json',ROOT/'data/processed/chunks.jsonl')
        self.assertEqual(len(dataset['questions']),16)
        self.assertFalse(dataset['configuration']['memory_enabled'])
        self.assertTrue(any(u['source_type']=='public' for q in dataset['questions'] for u in q['evidence_units']))

    def test_partial_cross_document_coverage_and_rank(self):
        row={'id':'a','page_content':'passage','metadata':{'incident_id':'A','title':'title','source_type':'synthetic','source':'a.json'}}
        question={'evidence_units':[{'incident_id':'A','acceptable_chunk_ids':['a']},{'incident_id':'B','acceptable_chunk_ids':['b']}]}
        result={'results':[{'id':'a','incident_id':'A','title':'title','source_type':'synthetic','source':'a.json','chunk_text':'passage'}]}
        metrics=retrieval_metrics(question,result,{'a':row})
        self.assertEqual(metrics['required_evidence_recall_at_5'],0.5)
        self.assertEqual(metrics['reciprocal_rank_at_5'],1)
        self.assertEqual(metrics['strict_judged_precision_at_5'],0.2)
        self.assertEqual(metrics['missing_evidence_incidents'],['B'])
        self.assertFalse(metrics['all_required_evidence_found'])
        self.assertEqual(metrics['metadata_errors'],[])

    def test_insufficient_questions_not_scored_as_retrieval_success(self):
        metrics=retrieval_metrics({'evidence_units':[]},{'results':[]},{})
        self.assertIsNone(metrics['hit_at_5'])
        self.assertIsNone(metrics['required_evidence_recall_at_5'])

    def test_unknown_sources_are_detected(self):
        metrics=retrieval_metrics({'evidence_units':[]},{'results':[{'id':'invented'}]}, {})
        self.assertTrue(metrics['metadata_errors'])
