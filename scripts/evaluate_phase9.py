"""Approved Phase 9 re-evaluation, with immutable baseline and cached retrieval."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.providers import ROOT,llm_provider
from src.incident_investigator.memory import memory_enabled
from src.incident_investigator.investigation import investigate
from src.incident_investigator.evaluation import load_dataset
from scripts.verify_phase6 import audit

OUT=ROOT/'data/processed/phase9'


def protected_unchanged():
    before=json.loads((OUT/'preservation_before.json').read_text())
    return [name for name,digest in before.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approve-llm',action='store_true',help='Only after explicit approval of up to 32 chat calls and 5–15 minute estimate')
    parser.add_argument('--run-id',choices=['run2'],default='run2')
    args=parser.parse_args()
    if not args.approve_llm: raise SystemExit('Approval required before any Ollama calls: up to 32 local chat requests; expected 5–15 minutes; no retries.')
    if memory_enabled(): raise SystemExit('Mem0 must remain disabled.')
    if protected_unchanged(): raise SystemExit('Baseline or protected configuration/data changed; review before running.')
    output=OUT/args.run_id
    output.mkdir(exist_ok=True)
    started=output/'generation_started.json'
    if started.exists(): raise SystemExit('Started run retained. No automatic repeat or overwrite.')
    dataset,_=load_dataset(ROOT/'evaluation/questions.json',ROOT/'data/processed/chunks.jsonl')
    cached=json.loads((ROOT/'data/processed/evaluation/retrieval.json').read_text())
    assert cached['dataset_sha256']==hashlib.sha256((ROOT/'evaluation/questions.json').read_bytes()).hexdigest()
    assert [r['question']['id'] for r in cached['rows']]==[q['id'] for q in dataset['questions']]
    started.write_text(json.dumps({'approved_chat_limit':32,'expected_minutes':[5,15],'no_retries':True,'started_unix':time.time()},indent=2))
    start=time.perf_counter();requests=[];rows=[];responses=[]
    for entry in cached['rows']:
        q=entry['question'];model=llm_provider();original=model.transport.request
        def counted(endpoint,body=None,timeout=180,original=original,identifier=q['id']):
            if endpoint=='/api/chat':
                if len(requests)>=32: raise RuntimeError('Approved chat limit reached')
                requests.append({'question_id':identifier,'request_number':len(requests)+1})
                (output/'chat_requests.json').write_text(json.dumps(requests,indent=2))
            response=original(endpoint,body,timeout)
            if endpoint=='/api/chat':
                responses.append({'question_id':identifier,'done':response.get('done'),'done_reason':response.get('done_reason'),'content':response.get('message',{}).get('content')})
                (output/'model_responses.json').write_text(json.dumps(responses,indent=2))
            return response
        model.transport.request=counted
        result=investigate(q['question'],llm=model,retriever=lambda _, cached=entry['retrieval']:cached)
        rows.append({'question':q,'result':result,'provenance_audit':audit(result)})
        (output/'generation_progress.json').write_text(json.dumps(rows,indent=2))
        print(q['id'],result['report']['status'],result['elapsed_seconds'],flush=True)
    (output/'generation.json').write_text(json.dumps({'rows':rows,'chat_request_count':len(requests),'elapsed_seconds':time.perf_counter()-start,'protected_files_changed':protected_unchanged(),'baseline_untouched':not protected_unchanged(),'note':'Qualitative review is separate; acceptance is not semantic accuracy.'},indent=2))
