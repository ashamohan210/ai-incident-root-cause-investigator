"""Publication inventory checks, not a rerun of historical RAG evaluation."""
import json
from collections import Counter
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PublicationTests(unittest.TestCase):
    def test_inventory_is_distinct_from_evaluated_dataset(self):
        data = json.loads((ROOT / 'evaluation/publication_safe/questions.json').read_text())
        self.assertIn('UNEVALUATED', data['status'])
        self.assertNotIn('chunk_file_sha256', data)
        self.assertEqual(Counter(q['category'] for q in data['questions']),
                         {'exact': 4, 'semantic': 5, 'cross_document': 3, 'insufficient': 4})
        for question in data['questions']:
            self.assertNotIn('evidence_units', question)
            for ref in question['reference_summaries']:
                self.assertNotIn('reference_quote', ref)
                self.assertTrue(ref['summary'])
                if ref['source_type'] == 'public':
                    self.assertTrue(ref['source_url'].startswith('https://'))

    def test_synthetic_generator_is_explicit_and_preserves_files(self):
        import phase2_incident_dataset as generator
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        with TemporaryDirectory() as folder:
            base = Path(folder)
            with patch.object(generator, 'SYNTHETIC', base/'synthetic'), patch.object(generator, 'PUBLIC', base/'public'), patch('builtins.print'):
                generator.generate()
                records = list((base/'synthetic').glob('*.json'))
                self.assertEqual(len(records), 20)
                before = {p: p.read_bytes() for p in records}
                generator.generate()
                self.assertEqual(before, {p: p.read_bytes() for p in records})
                for p in records:
                    data = json.loads(p.read_text())
                    self.assertEqual(data['source_type'], 'synthetic')
                    self.assertIn('SYNTHETIC TEST DATA', data['full_report'])

    def test_safe_reviews_preserve_historical_numerical_counts(self):
        data = json.loads((ROOT/'evaluation/publication_safe/phase9_answer_reviews.json').read_text())
        questions = data['questions'].values()
        self.assertEqual(sum(q['reviewed_historical_claims'] for q in questions), 45)
        self.assertEqual(sum(q['supported_historical_claims'] for q in questions), 42)
