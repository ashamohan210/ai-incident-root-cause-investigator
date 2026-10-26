"""Explicit live Streamlit smoke demo. Uses real services within the existing memory ledger.

Runs once per output directory to avoid accidentally repeating paid operations.
No RAG evaluation, embedding regeneration, or Pinecone writes.
"""
import hashlib
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest
from scripts.verify_phase6 import audit
from src.incident_investigator.memory import UsageGuard, memory_enabled

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/phase8'


def save(name, data):
    (OUT / (name + '.json')).write_text(json.dumps(data, indent=2))


def button(app, label):
    return next(b for b in app.button if b.label == label)


def turn(app):
    assert not app.exception, 'Streamlit exception'
    workspace = app.session_state['workspaces'][app.session_state['active_investigation']]
    assert workspace['turns'], 'No completed UI turn'
    return workspace['turns'][-1]


def snapshot():
    files = list((ROOT / 'data/incidents').glob('*/*.json')) + [ROOT / 'data/processed/chunks.jsonl', ROOT / 'data/local_embeddings/embeddings.jsonl']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


if __name__ == '__main__':
    if not memory_enabled():
        raise SystemExit('Archived hosted-memory demo disabled. No service calls were made.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='data/processed/phase8')
    args = parser.parse_args()
    OUT = (ROOT / args.output_dir).resolve()
    if not OUT.is_relative_to(ROOT / 'data/processed'):
        raise SystemExit('Output must be under data/processed.')
    OUT.mkdir(parents=True, exist_ok=True)
    guardfile = OUT / 'live_started.json'
    if guardfile.exists():
        raise SystemExit('This live demo was already started. Review existing artifacts; no automatic repeat.')
    before = UsageGuard().snapshot()
    if before.get('writes', 0) > 6 or before.get('reads', 0) > 20:
        raise SystemExit('Insufficient remaining approved memory budget for this demo.')
    save('live_started', {'started_at_unix': time.time(), 'usage_before': before, 'automatic_retries': 0})
    hashes = snapshot(); save('preservation_before', hashes)
    app = AppTest.from_file(str(ROOT / 'app.py'))
    app.query_params['investigation'] = 'phase8-payments-ui-v1'
    app.run(timeout=30)
    initial_session = app.session_state['ui_session_id']
    app.text_area[0].input('Investigate HTTP 503 errors after deployment with unusually high database connections. We checked the database connection pool.')
    button(app, 'Run investigation').click().run(timeout=240)
    initial = turn(app); save('incident', initial)
    print('Incident:', initial['result']['report']['status'], initial['duration_seconds'], flush=True)
    # Same UI session and scope, but an explicit separate conversation turn.
    next(x for x in app.text_input if x.label == 'Follow-up question').input('What checks have we already performed?')
    button(app, 'Send follow-up').click().run(timeout=240)
    followup = turn(app); save('followup', followup)
    print('Follow-up:', followup['result']['report']['status'], followup['duration_seconds'], flush=True)
    # A fresh WebSocket-equivalent session resumes via the public UI control.
    resumed = AppTest.from_file(str(ROOT / 'app.py'))
    resumed.query_params['investigation'] = 'phase8-payments-ui-v1'
    resumed.run(timeout=30)
    button(resumed, 'Open / resume investigation').click().run(timeout=90)
    saved = resumed.session_state['workspaces']['phase8-payments-ui-v1']['memories']
    save('resumed_context', saved)
    unknown = AppTest.from_file(str(ROOT / 'app.py'))
    unknown.query_params['investigation'] = 'phase8-unrelated-ui-v1'
    unknown.run(timeout=30)
    unknown.checkbox[0].uncheck()
    unknown.text_area[0].input('Quantum processor decoherence following helium purge')
    button(unknown, 'Run investigation').click().run(timeout=240)
    insufficient = turn(unknown); save('insufficient', insufficient)
    after = UsageGuard().snapshot()
    checks = {
        'incident_report_accepted': initial['result']['report']['status'] == 'investigation',
        'historical_claim_audit': audit(initial['result'])['passed'],
        'memory_followup_recalled_check': any('checked the database connection pool' in r['text'] for r in followup['result']['report'].get('completed_checks', [])),
        'resume_new_session': resumed.session_state['ui_session_id'] != initial_session,
        'resume_restored_context': any(r['metadata']['kind'] == 'completed_check' for r in saved),
        'insufficient_evidence': insufficient['result']['report']['status'] == 'insufficient_evidence',
        'source_data_unchanged': hashes == snapshot(),
        'no_streamlit_exceptions': not any(a.exception for a in (app, resumed, unknown)),
    }
    summary = {'checks': checks, 'all_passed': all(checks.values()), 'timings_seconds': {'incident': initial['duration_seconds'], 'followup': followup['duration_seconds'], 'insufficient': insufficient['duration_seconds']},
        'run_api_usage': {key: after.get(key, 0) - before.get(key, 0) for key in ('reads', 'writes', 'connectivity_checks', 'deletions')},
        'cumulative_api_usage': {key: after.get(key, 0) for key in ('reads', 'writes', 'connectivity_checks', 'deletions')}, 'historical_claim_audit': audit(initial['result']), 'credit_usage': after['credit_usage']}
    save('verification_summary', summary)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary['all_passed'] else 1)
