"""Offline Phase 9 comparison; never writes baseline artifacts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'data/processed/phase9/run2'
baseline=json.loads((ROOT/'data/processed/evaluation/answer_metrics.json').read_text())
g=json.loads((p/'generation.json').read_text());reviews=json.loads((ROOT/'evaluation/phase9_answer_reviews.json').read_text())
assert set(reviews['questions'])=={row['question']['id'] for row in g['rows']}
counts={'accepted_answerable':0,'false_refusals':0,'safe_insufficient':0,'expected_behavior_passes':0,'historical_claims':0,'valid_citations':0,'supported_historical':0,'hypotheses':0,'supported_hypotheses':0}
for row in g['rows']:
 q=row['question'];r=row['result']['report'];review=reviews['questions'][q['id']]
 claims=sum(len(r[k]) for k in ['historical_root_causes','historical_observations','previous_resolutions'])
 hypotheses=len(r['current_incident_hypotheses'])
 assert review['reviewed_historical_claims']==claims and review['reviewed_hypotheses']==hypotheses
 assert 0<=review['supported_historical_claims']<=claims and 0<=review['supported_hypotheses']<=hypotheses
 if q['answerable']:
  counts['accepted_answerable']+=r['status']=='investigation';counts['false_refusals']+=r['status']=='insufficient_evidence'
 else: counts['safe_insufficient']+=bool(review['unsupported_requested_facts_withheld'])
 counts['expected_behavior_passes']+=bool(review['expected_behavior_pass'])
 counts['historical_claims']+=claims;counts['valid_citations']+=claims if row['provenance_audit']['passed'] else 0
 counts['supported_historical']+=review['supported_historical_claims'];counts['hypotheses']+=hypotheses;counts['supported_hypotheses']+=review['supported_hypotheses']
mean_positive=sum(row['result']['elapsed_seconds'] for row in g['rows'] if row['question']['answerable'])/12
old=json.loads((ROOT/'data/processed/evaluation/generation.json').read_text())
old_mean=sum(row['result']['elapsed_seconds'] for row in old['rows'] if row['question']['answerable'])/12
counts['unclear_historical']=sum(len(review.get('unclear_historical_indices',[])) for review in reviews['questions'].values())
counts['contradicted_historical']=sum(len(review.get('contradicted_historical_indices',[])) for review in reviews['questions'].values())
summary={'counts':counts,'actual_chat_requests':g['chat_request_count'],'elapsed_seconds':g['elapsed_seconds'],'mean_answerable_seconds':mean_positive,'baseline_mean_answerable_seconds':old_mean,'review_method':reviews['review_method'],'baseline_untouched':g['baseline_untouched'],'comparison_scope':'Same questions/cached retrieval. Development-set comparison after extractive redesign, not held-out generalization.'}
(p/'comparison_metrics.json').write_text(json.dumps(summary,indent=2))
target=ROOT/'evaluation/PHASE9_REPORT.md'
text=target.read_text();prefix=text.split('## Proposed approved evaluation')[0].split('## Before-and-after evaluation')[0].split('## First experiment comparison')[0]
prefix=prefix.replace('**81 regression tests passed:** existing 69 tests plus 12 targeted reliability','**83 regression tests passed:** existing 69 tests plus 14 targeted reliability')
prefix=prefix.replace('**Status: first approved experiment reviewed; a safer public-observation revision\npasses 83 offline tests but requires a separately approved model re-evaluation.**','**Status: safer-revision implementation, offline tests, separately approved re-evaluation, and coding-assistant review complete.**')
prefix=prefix.replace('**Status: implementation and offline verification complete. Live re-evaluation\nrequires explicit approval; no Phase 9 Ollama calls have been made yet.**','**Status: implementation, offline verification, approved 16-question re-evaluation,\nand coding-assistant qualitative review complete.**')
lines=[prefix,'## Before-and-after evaluation','', '| Measure | Original baseline | Phase 9 |','| --- | --- | --- |',
 f"| Accepted answerable reports | 5/12 | {counts['accepted_answerable']}/12 |",
 f"| False refusals | 7/12 | {counts['false_refusals']}/12 |",
 f"| Historical citation provenance | 16/16 | {counts['valid_citations']}/{counts['historical_claims']} |",
 f"| Supported exposed historical claims/hypotheses | 24/25 | {counts['supported_historical']+counts['supported_hypotheses']}/{counts['historical_claims']+counts['hypotheses']} |",
 f"| Correct insufficient responses | 4/4 | {counts['safe_insufficient']}/4 |",
 f"| Overall expected behavior | 8/16 | {counts['expected_behavior_passes']}/16 |",
 f"| Actual local chat requests | 28 | {g['chat_request_count']} (cap 32) |",
 f"| Total generation-stage seconds | {baseline['elapsed_seconds']:.3f} | {g['elapsed_seconds']:.3f} |",
 f"| Mean answerable response seconds | {old_mean:.3f} | {mean_positive:.3f} |",'',
 'Both runs reused the same cached retrieval. No new Pinecone, Mem0, or judge-model calls were made. Existing model configuration and citation rules were retained, with stronger span/selection checks. Hypotheses are now extractive templates rather than free-form causal paraphrases; support scores therefore compare different output expressiveness, not pure model intelligence.','',
 '## Per-question review and remaining failures','', '| ID | Phase 9 status | Seconds | Expected behavior | Review |','| --- | --- | --- | --- | --- |']
for row in g['rows']:
 q=row['question'];review=reviews['questions'][q['id']]
 lines.append(f"| {q['id']} | {row['result']['report']['status']} | {row['result']['elapsed_seconds']:.3f} | {'pass' if review['expected_behavior_pass'] else 'fail'} | {review['reason'].replace('|','/')} |")
first=json.loads((ROOT/'data/processed/phase9/comparison_metrics.json').read_text())
lines+=['','## Preserved first experiment','',f"The first separately approved run used **{first['actual_chat_requests']}** chat calls in **{first['elapsed_seconds']:.3f} seconds**. It accepted **{first['counts']['accepted_answerable']}/12** answerable cases, but review found **2 unsupported public root-cause labels**. Those results were not treated as a successful release. The safer revision removes automatic role labeling of public prose and adds source titles. First-run report/reviews/raw outputs remain intact.", '',f"Across the two separately approved runs, actual chat requests total **{first['actual_chat_requests']+g['chat_request_count']}**. Each approval capped its run at 32; no retries or additional retrieval were used."]
lines+=['','## Interpretation and limitations','',reviews['review_method'],'',
 f"Strict exposed-claim support is **{counts['supported_historical']+counts['supported_hypotheses']}/{counts['historical_claims']+counts['hypotheses']}**, compared with baseline 24/25. The revised run has **{counts['unclear_historical']} unclear public fragments**, not counted as supported, and **{counts['contradicted_historical']} identified source contradictions**. Thus acceptance improved, but a faithfulness improvement must not be claimed. All current-hypothesis lists were empty in this factual/comparison set, so live hypothesis support is not measurable in this run. Offline mechanism tests cover actor/negation preservation.", '',
 'Exact excerpts prevent invented quotes and actor/negation rewrites, but they do not prove that the selected fact answers the question. Public prose stays as neutral observations; no automatic public causal/resolution classification is asserted. Markers affect excerpt salience only. Additional unrequested sources, duplicate facts, incomplete answers, or fact-kind ambiguity remain possible. Generic diagnostic guidance is less tailored than the former free-form output.','',
 'The same development set informed this redesign. These before/after results are not independently blinded or held-out production accuracy. No production inference was changed during the re-evaluation. All invalid selections still fail closed; no fuzzy quote matching or acceptance threshold relaxation was introduced.','',
 '## Verification and files','',
 '**83 regression tests passed** (69 prior tests with schema fixtures adapted, plus 14 new reliability tests). `pip check` found no broken requirements. Protected baseline, source, embedding, environment, and Mem0-ledger hashes are checked separately in `verification_summary.json`. The Streamlit interface and session-only behavior are unchanged and covered by the regression suite.','',
 'Runtime changes: `src/incident_investigator/evidence_catalog.py` and `investigation.py`. Tests: `test_reliability.py`, updated generation fixtures in `test_investigation.py`, and one archived fake-memory fixture. New tooling: `scripts/evaluate_phase9.py`, `scripts/report_phase9.py`. New report/review: this file and `evaluation/phase9_answer_reviews.json`. README/architecture documentation describes the active behavior. Baseline artifacts were not overwritten.','',
 'Raw results and call accounting: `data/processed/phase9/run2/generation.json`, `chat_requests.json`, `comparison_metrics.json`; offline tests are in `data/processed/phase9/regression_tests.txt`. The first experiment remains under the parent directory and in `PHASE9_RUN1_REPORT.md`. Source references were selected only from runtime retrieval; there are no evaluation IDs or prewritten question answers in the generation code.']
target.write_text('\n'.join(lines)+'\n');print(json.dumps(summary,indent=2))
