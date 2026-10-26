"""Run retrieval first; full generation requires explicit approval via --approve-llm."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.providers import ROOT
from src.incident_investigator.memory import memory_enabled
from src.incident_investigator.retrieval import hybrid_search
from src.incident_investigator.evaluation import load_dataset, retrieval_metrics, aggregate


def preservation():
    paths = list((ROOT/'data/incidents').glob('*/*.json')) + [ROOT/'data/processed/chunks.jsonl',ROOT/'data/local_embeddings/embeddings.jsonl',ROOT/'data/memory/phase7_usage.json',ROOT/'config/providers.toml',ROOT/'config/retrieval.toml',ROOT/'config/memory.toml',ROOT/'.env']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['retrieval','generation'])
    parser.add_argument('--approve-llm',action='store_true',help='Use only after approval of model-call count and runtime')
    args=parser.parse_args()
    if memory_enabled(): raise SystemExit('Memory must remain disabled for this evaluation.')
    if args.stage=='generation' and not args.approve_llm:
        raise SystemExit('Approval required: at most 32 local chat requests, expected 15–25 minutes, no automatic retries.')
    dataset,chunks=load_dataset(ROOT/'evaluation/questions.json',ROOT/'data/processed/chunks.jsonl')
    output=ROOT/'data/processed/evaluation';output.mkdir(exist_ok=True)
    target=output/(args.stage+'.json')
    started_file=output/(args.stage+'_started.json')
    if target.exists() or started_file.exists(): raise SystemExit('Existing run retained; review artifacts before authorizing another run.')
    if args.stage=='generation' and not (output/'retrieval.json').exists(): raise SystemExit('Run retrieval first.')
    before=preservation();started_file.write_text(json.dumps({'preservation':before,'started_unix':time.time()},indent=2))
    rows=[];start=time.perf_counter()
    if args.stage=='retrieval':
        for question in dataset['questions']:
            phase=time.perf_counter()
            result=hybrid_search(question['question'])
            row={'question':question,'retrieval':result,'metrics':retrieval_metrics(question,result,chunks),'elapsed_seconds':round(time.perf_counter()-phase,3)}
            rows.append(row)
            (output/'retrieval_progress.json').write_text(json.dumps(rows,indent=2))
            print(question['id'],row['metrics']['required_evidence_recall_at_5'],row['elapsed_seconds'],flush=True)
        summary=aggregate(rows)
        summary['by_category']={category:aggregate([r for r in rows if r['question']['category']==category]) for category in ['exact','semantic','cross_document']}
        summary['elapsed_seconds']=round(time.perf_counter()-start,3)
        target.write_text(json.dumps({'dataset_sha256':hashlib.sha256((ROOT/'evaluation/questions.json').read_bytes()).hexdigest(),'rows':rows,'summary':summary,'preservation_unchanged':before==preservation()},indent=2))
        print(json.dumps(summary,indent=2))
    else:
        from src.incident_investigator.investigation import investigate
        from scripts.verify_phase6 import audit
        cache=json.loads((output/'retrieval.json').read_text())
        if cache['dataset_sha256']!=hashlib.sha256((ROOT/'evaluation/questions.json').read_bytes()).hexdigest(): raise SystemExit('Dataset changed since retrieval.')
        from src.incident_investigator.providers import llm_provider
        chat_requests = []
        for row in cache['rows']:
            question=row['question']
            llm = llm_provider()
            original_request = llm.transport.request
            def counted_request(endpoint, body=None, timeout=180, original=original_request, question_id=question['id']):
                if endpoint == '/api/chat':
                    if len(chat_requests) >= 32:
                        raise RuntimeError('Approved chat request budget exhausted')
                    chat_requests.append({'question_id':question_id,'request_number':len(chat_requests)+1})
                    (output/'chat_requests.json').write_text(json.dumps(chat_requests,indent=2))
                return original(endpoint, body, timeout)
            llm.transport.request = counted_request
            result=investigate(question['question'],llm=llm,retriever=lambda _, cached=row['retrieval']:cached)
            report=result['report']
            rows.append({'question':question,'result':result,'provenance_audit':audit(result),
                         'expected_insufficient':not question['answerable'],'returned_insufficient':report['status']=='insufficient_evidence',
                         'human_faithfulness_review':None,'human_citation_entailment_review':None,'human_expected_behavior_review':None})
            (output/'generation_progress.json').write_text(json.dumps(rows,indent=2))
            print(question['id'],report['status'],flush=True)
        target.write_text(json.dumps({'rows':rows,'elapsed_seconds':time.perf_counter()-start,'preservation_unchanged':before==preservation(),'chat_request_count':len(chat_requests),'note':'Exact quote audits are automated; semantic faithfulness and question-level abstention require human review.'},indent=2))
