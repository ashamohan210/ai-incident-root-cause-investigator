"""Score saved answers plus explicit analyst review; no model or service calls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'data/processed/evaluation'
g=json.loads((p/'generation.json').read_text())
reviews=json.loads((ROOT/'evaluation/answer_reviews.json').read_text())
assert set(reviews['questions'])=={row['question']['id'] for row in g['rows']}
counts={'exposed_historical_claims':0,'automatically_valid_historical_citations':0,'analyst_supported_claims':0,'analyst_reviewed_claims':0,'supported_hypotheses':0,'reviewed_hypotheses':0,'answerable_questions':0,'answerable_nonabstentions':0,'insufficient_questions':0,'safe_insufficient_responses':0,'correct_insufficient_statuses':0,'false_refusals':0,'expected_behavior_passes':0}
for row in g['rows']:
 q=row['question'];r=row['result']['report'];review=reviews['questions'][q['id']]
 claims=sum(len(r.get(k,[])) for k in ['historical_root_causes','previous_resolutions','historical_observations'])
 hypotheses=len(r.get('current_incident_hypotheses',[]))
 assert review['reviewed_historical_claims']==claims,(q['id'],'wrong claim denominator')
 assert review['reviewed_hypotheses']==hypotheses,(q['id'],'wrong hypothesis denominator')
 assert 0<=review['supported_historical_claims']<=claims
 assert 0<=review['supported_hypotheses']<=hypotheses
 counts['exposed_historical_claims']+=claims
 if row['provenance_audit']['passed']:counts['automatically_valid_historical_citations']+=claims
 counts['analyst_reviewed_claims']+=claims;counts['analyst_supported_claims']+=review['supported_historical_claims']
 counts['reviewed_hypotheses']+=hypotheses;counts['supported_hypotheses']+=review['supported_hypotheses']
 counts['expected_behavior_passes']+=bool(review['expected_behavior_pass'])
 if q['answerable']:
  counts['answerable_questions']+=1
  counts['answerable_nonabstentions']+=r['status']=='investigation'
  counts['false_refusals']+=r['status']=='insufficient_evidence'
 else:
  counts['insufficient_questions']+=1
  counts['safe_insufficient_responses']+=bool(review['unsupported_requested_facts_withheld'])
  counts['correct_insufficient_statuses']+=r['status']=='insufficient_evidence'
def ratio(a,b):return counts[a]/counts[b] if counts[b] else None
summary={'counts':counts,'combined_claim_support':(counts['analyst_supported_claims']+counts['supported_hypotheses'])/(counts['analyst_reviewed_claims']+counts['reviewed_hypotheses']) if counts['analyst_reviewed_claims']+counts['reviewed_hypotheses'] else None,'faithfulness_exposed_historical_claims':ratio('analyst_supported_claims','analyst_reviewed_claims'),'hypothesis_support':ratio('supported_hypotheses','reviewed_hypotheses'),'automated_citation_provenance_validity':ratio('automatically_valid_historical_citations','exposed_historical_claims'),'answerable_response_coverage':ratio('answerable_nonabstentions','answerable_questions'),'false_refusal_rate':ratio('false_refusals','answerable_questions'),'safe_insufficient_handling':ratio('safe_insufficient_responses','insufficient_questions'),'insufficient_status_rate':ratio('correct_insufficient_statuses','insufficient_questions'),'expected_behavior_pass_rate':counts['expected_behavior_passes']/16,'actual_chat_requests':g['chat_request_count'],'elapsed_seconds':g['elapsed_seconds'],'review_method':reviews['review_method'],'caveat':'Claim faithfulness/provenance only measure exposed claims. Rejections and missing required evidence reduce coverage and expected-behavior scores; empty answers are not faithfulness successes.'}
summary['by_category']={category:{'questions':sum(row['question']['category']==category for row in g['rows']),'expected_behavior_passes':sum(bool(reviews['questions'][row['question']['id']]['expected_behavior_pass']) for row in g['rows'] if row['question']['category']==category)} for category in ['exact','semantic','cross_document','insufficient']}
(p/'answer_metrics.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
