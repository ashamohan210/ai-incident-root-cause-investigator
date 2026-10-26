"""Produce an honest retrieval-stage report from saved measurements; no API calls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'data/processed/evaluation'
r=json.loads((p/'retrieval.json').read_text());s=r['summary']
lines=['# Gen Academy Week 2 — RAG Evaluation Report','',
'**Status: retrieval stage complete; full generation and answer review await approval.**','',
'## Application and dataset','',
'34 incident reports (20 synthetic, 14 public), 104 chunks and cached 768-dimensional EmbeddingGemma vectors. Existing Pinecone Documents API hybrid search, RRF and local MiniLM were evaluated unchanged. Qwen generation is deferred. Mem0 is disabled and excluded; session-only conversations are unchanged.','',
'16 questions: 4 exact, 5 semantic, 3 cross-document, 4 insufficient-evidence. Reference judgments are corpus-derived, not independently blinded. See `evaluation/questions.json` and `evaluation/PLAN.md`.','',
'## Actual retrieval results','',
'Positive metrics use the 12 answerable questions; four insufficient cases have no positive retrieval labels. Retrieval errors count as misses. Strict precision uses only curated reference passages, so relevant unlabeled passages can be penalized.','',
'| Metric | Actual value |','| --- | --- |']
position = lines.index('## Actual retrieval results')
dataset_lines = ['## The 16 evaluation questions', '', '| ID | Category | Question | Required reference incidents |', '| --- | --- | --- | --- |']
for row in r['rows']:
 q=row['question']; references=', '.join(u['incident_id'] for u in q['evidence_units']) or 'No supported answer expected'
 dataset_lines.append(f"| {q['id']} | {q['category']} | {q['question'].replace('|','/')} | {references} |")
lines[position:position] = dataset_lines + ['']
for key in ['required_evidence_recall_at_5','hit_at_5','reciprocal_rank_at_5','strict_judged_precision_at_5','all_required_evidence_found']:
 lines.append(f'| {key} | {s[key]:.4f} |')
lines+=['',f"Elapsed retrieval-run time: **{s['elapsed_seconds']:.3f} seconds**. Errors: **{s['retrieval_errors']}**; degraded questions: **{s['degraded_questions']}**; reranking active: **{s['reranking_active_questions']}/16**; metadata/text errors: **{s['metadata_errors']}**. These are observed outputs, not billing measurements.",'',
'| Category | Questions | Required-evidence recall@5 | MRR@5 | Complete-evidence rate |', '| --- | --- | --- | --- | --- |']
for cat,a in s['by_category'].items():lines.append(f"| {cat} | {a['answerable_questions']} | {a['required_evidence_recall_at_5']:.4f} | {a['reciprocal_rank_at_5']:.4f} | {a['all_required_evidence_found']:.4f} |")
lines+=['','## Per-question results and failure analysis','','| ID | Category | Top five incidents in rank order | Required evidence missed | Seconds |','| --- | --- | --- | --- | --- |']
for row in r['rows']:
 q=row['question'];m=row['metrics'];ids=', '.join(x['incident_id'] for x in row['retrieval'].get('results',[])[:5]);missing=', '.join(m['missing_evidence_incidents']) if q['answerable'] else 'Not applicable: answer abstention pending'
 lines.append(f"| {q['id']} | {q['category']} | {ids or 'none'} | {missing or 'none'} | {row['elapsed_seconds']:.3f} |")
lines+=['','Misses below concern frozen required passages, not a universal judgment that all other returned material is irrelevant. No ranking parameters were tuned against this dataset.','']
for row in r['rows']:
 q=row['question'];m=row['metrics']
 if q['answerable'] and m['missing_evidence_incidents']:
  lines.append(f"- **{q['id']}** missed {', '.join(m['missing_evidence_incidents'])}. Review raw chunk ranks and content in `retrieval.json`; additional relevant passages may have crowded out the required evidence. The measurements alone do not identify whether semantic retrieval, fusion, or reranking caused the miss.")
 if row['retrieval'].get('error'):lines.append(f"- **{q['id']}** had a retrieval service error; treat as availability failure, not successful retrieval.")
lines+=['','Insufficient-evidence queries can still return nearest neighbors. Their existence does not demonstrate answerability or a model hallucination. Current-production values, attacker attribution, or unrelated domain facts must not be inferred from similar historical reports.','',
'## Answer quality — not yet measured','',
'**Faithfulness, generated citation correctness, expected-answer coverage, false refusals, and insufficient-evidence handling are pending.** No generated answers were produced in this stage. Retrieval metadata agreement is not a generated-citation score. Analyst review must assess semantic entailment, not only exact quotations.','',
'Generation proposal: 16 independent questions, at most **32 local Qwen chat calls**, expected **15–25 minutes**, no retries or judge-model calls. Reuse saved retrieval, with no additional Pinecone searches or document embedding generation. Explicit approval is required before execution.','',
'## Verification and limitations','',
f"Protected data/configuration/environment/ledger hashes unchanged: **{r['preservation_unchanged']}**. Pinecone operations were read-only. No Mem0 operations, model changes, schema changes, or source mutations were requested by the runner.", '',
'All **69 regression tests passed**, including the existing 65 and four evaluation-helper tests; `pip check` found no broken requirements. Detailed outcomes are in `regression_tests.txt` and the final verification summary. Prior sandbox network failures are archived separately and are not presented as ranking results.','',
'This is a small, manually curated, corpus-specific test set with incomplete relevance labels. Synthetic incidents are fictional examples. Do not generalize these measurements to production accuracy, or present this staged report as a completed answer-quality evaluation.']
if (p/'answer_metrics.json').exists():
 a=json.loads((p/'answer_metrics.json').read_text())
 g=json.loads((p/'generation.json').read_text())
 reviews=json.loads((ROOT/'evaluation/answer_reviews.json').read_text())
 lines[2]='**Status: retrieval, approved generation, and coding-assistant qualitative review complete. Independent human review was not performed.**'
 lines=[line.replace('Qwen generation is deferred.','Qwen generation was evaluated using the saved retrieval results.') for line in lines]
 start=lines.index('## Answer quality — not yet measured');end=lines.index('## Verification and limitations')
 answer=['## Actual answer-quality results','', '| Measure | Actual numerator / denominator | Result |','| --- | --- | --- |']
 counts=a['counts']
 for label,key,numerator,denominator in [
   ('Historical claim support (analyst review)','faithfulness_exposed_historical_claims','analyst_supported_claims','analyst_reviewed_claims'),
   ('Hypothesis support (analyst review)','hypothesis_support','supported_hypotheses','reviewed_hypotheses'),
   ('Automated citation provenance validity','automated_citation_provenance_validity','automatically_valid_historical_citations','exposed_historical_claims'),
   ('Answerable response coverage','answerable_response_coverage','answerable_nonabstentions','answerable_questions'),
   ('False-refusal rate','false_refusal_rate','false_refusals','answerable_questions'),
   ('Safe insufficient-evidence handling','safe_insufficient_handling','safe_insufficient_responses','insufficient_questions'),
   ('Insufficient status on negative questions','insufficient_status_rate','correct_insufficient_statuses','insufficient_questions')]:
  value='Not measurable (no exposed claims)' if a[key] is None else f"{a[key]:.2%}"
  answer.append(f"| {label} | {counts[numerator]} / {counts[denominator]} | {value} |")
 answer+=['',f"Combined exposed-claim support (historical claims plus unconfirmed hypotheses): **{counts['analyst_supported_claims']+counts['supported_hypotheses']}/{counts['analyst_reviewed_claims']+counts['reviewed_hypotheses']} ({a['combined_claim_support']:.2%})**. This is coding-assistant review, not independent human adjudication.",'',f"Expected-behavior passes: **{counts['expected_behavior_passes']}/16**. Actual local chat requests: **{a['actual_chat_requests']}** (approved maximum 32); total generation-stage runtime: **{a['elapsed_seconds']:.3f} seconds**. No additional retrieval or judge-model calls were used.",'',
  '**Interpretation:** exposed-claim validity is conditional on fail-closed filtering; it does not count refused or empty answers as faithful successes. Response coverage and false refusals show the usability cost. Analyst support judgments were made by the coding assistant against saved passages, not by a blinded human reviewer or separate judge-model API.','',
  '| ID | Status | Generation-stage seconds | Expected behavior | Review / failure |', '| --- | --- | --- | --- | --- |']
 for row in g['rows']:
  q=row['question'];review=reviews['questions'][q['id']]
  answer.append(f"| {q['id']} | {row['result']['report']['status']} | {row['result']['elapsed_seconds']:.3f} | {'pass' if review['expected_behavior_pass'] else 'fail'} | {review['reason'].replace('|','/')} |")
 answer+=['','### Failure analysis and next steps','',
  'Six answerable cases failed hypothesis-citation alignment (E01–E04, S01, C01); S05 failed exact quotation checks. C03 passed automated validation but contains a semantic error: it reverses which DNS server failed to restart. The source says only the authoritative server restarted, while the hypothesis says that server did not restart. S03/C02 also retain stronger-than-ideal wording inside otherwise unconfirmed hypotheses. These problems were not patched during the evaluation.', '',
  'All positive reference units were retrieved, so missing required passages do not explain these particular answer failures. Rejected drafts and conservative abstentions are recorded individually above. No prompts, models, index settings, or citation rules were changed during this evaluation.','',
  'Safe future work: improve structured-output/citation-ID alignment, bound the number of hypotheses, and make the answer schema suitable for factual questions and cross-document comparisons. Preserve source-membership and exact-quote checks. Test changes against a separate held-out set; do not tune to these 16 questions and then describe the same scores as unbiased validation. These are recommendations, not implemented changes.','']
 lines=lines[:start]+answer+lines[end:]
 lines=[line.replace('or present this staged report as a completed answer-quality evaluation.', 'or treat this small completed run as comprehensive production validation.') for line in lines]
 lines.append('\nFull generated outputs: `data/processed/evaluation/generation.json`; per-question review: `evaluation/answer_reviews.json`; metrics: `data/processed/evaluation/answer_metrics.json`.')
(ROOT/'evaluation/REPORT.md').write_text('\n'.join(lines)+'\n')
print('Wrote evaluation/REPORT.md from measured retrieval artifacts.')
