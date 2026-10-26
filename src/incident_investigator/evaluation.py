"""Corpus-grounded evaluation helpers; no service calls in this module."""
import hashlib
import json
from collections import Counter
from pathlib import Path


def load_dataset(path, chunk_path):
    dataset = json.loads(Path(path).read_text())
    assert Counter(q['category'] for q in dataset['questions']) == {'exact':4,'semantic':5,'cross_document':3,'insufficient':4}, 'Wrong question distribution'
    assert len({q['id'] for q in dataset['questions']}) == 16, 'Duplicate question IDs'
    assert hashlib.sha256(Path(chunk_path).read_bytes()).hexdigest() == dataset['chunk_file_sha256'], 'Corpus changed; re-review judgments'
    chunks = {r['id']:r for r in map(json.loads, Path(chunk_path).read_text().splitlines())}
    for q in dataset['questions']:
        assert q['answerable'] == bool(q['evidence_units'])
        for unit in q['evidence_units']:
            for identifier in unit['acceptable_chunk_ids']:
                row = chunks[identifier]
                assert row['metadata']['incident_id'] == unit['incident_id']
                assert unit['reference_quote'] in row['page_content'], 'Reference quote not in corpus'
                if unit.get('reference_resolution'):
                    assert unit['reference_resolution'] in row['page_content'], 'Resolution not in corpus'
    return dataset, chunks


def retrieval_metrics(question, result, chunks):
    rows = result.get('results', [])[:5]
    ids = [r['id'] for r in rows]
    units = question['evidence_units']
    gold = {identifier for u in units for identifier in u['acceptable_chunk_ids']}
    hits = sum(any(i in ids for i in u['acceptable_chunk_ids']) for u in units)
    relevant_ranks = [rank for rank, identifier in enumerate(ids,1) if identifier in gold]
    metadata_errors = []
    for row in rows:
        reference = chunks.get(row['id'])
        if reference is None:
            metadata_errors.append(row['id']+': unknown chunk')
            continue
        for key, source_key in [('incident_id','incident_id'),('title','title'),('source_type','source_type'),('source','source'),('source_url','source_url')]:
            if row.get(key) != reference['metadata'].get(source_key): metadata_errors.append(row['id']+': '+key)
        if row.get('chunk_text') != reference['page_content']: metadata_errors.append(row['id']+': text mismatch')
    return {'required_evidence_recall_at_5':hits/len(units) if units else None,
            'hit_at_5':bool(relevant_ranks) if units else None,
            'reciprocal_rank_at_5':1/relevant_ranks[0] if relevant_ranks else (0.0 if units else None),
            'strict_judged_precision_at_5':sum(i in gold for i in ids)/5 if units else None,
            'all_required_evidence_found':hits==len(units) if units else None,
            'missing_evidence_incidents':[u['incident_id'] for u in units if not any(i in ids for i in u['acceptable_chunk_ids'])],
            'returned_count':len(rows),'metadata_errors':metadata_errors,'duplicate_ids':len(ids)-len(set(ids))}


def aggregate(rows):
    answerable = [r for r in rows if r['question']['answerable']]
    keys = ['required_evidence_recall_at_5','reciprocal_rank_at_5','strict_judged_precision_at_5','hit_at_5','all_required_evidence_found']
    return {**{key:sum(r['metrics'][key] for r in answerable)/len(answerable) for key in keys},
            'answerable_questions':len(answerable),'total_questions':len(rows),
            'retrieval_errors':sum(bool(r['retrieval'].get('error')) for r in rows),
            'degraded_questions':sum(bool(r['retrieval'].get('warnings')) for r in rows),
            'metadata_errors':sum(len(r['metrics']['metadata_errors']) for r in rows),
            'reranking_active_questions':sum(bool(r['retrieval'].get('reranking',{}).get('active')) for r in rows),
            'answer_faithfulness':None,'generated_citation_correctness':None,'insufficient_evidence_handling':None,
            'pending_reason':'Answer metrics require approved LLM runs and documented human review; nearest neighbors do not prove answerability.'}
