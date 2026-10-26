> PUBLICATION COPY: explanatory wording may be paraphrased; historical measurements are unchanged. The original local artifact is preserved and excluded from Git. Links to `evaluation/questions.json` identify the original evaluated dataset, which is not distributed. `questions.json` beside this file is an unevaluated summary inventory.

# Phase 9 — Investigation reliability improvements

**Status: implementation, offline verification, approved 16-question re-evaluation,
and coding-assistant qualitative review complete.**

## Baseline diagnosis

The original `evaluation/REPORT.md`, questions, reviews, and raw results are
preserved. Source/configuration/baseline SHA-256 snapshots are saved in
`data/processed/phase9/preservation_before.json`.

| False-refusal case | Observed rejection |
| --- | --- |
| E01 | Three hypothesis references failed the validated/retrieved citation condition |
| E02 | Two hypothesis references failed that condition |
| E03 | One hypothesis reference failed that condition |
| E04 | One hypothesis reference failed that condition; a factual-duration question was forced to have a current hypothesis |
| S01 | One hypothesis reference failed that condition |
| C01 | One hypothesis reference failed that condition in a three-incident comparison |
| S05 | Three quotations did not occur in the cited public timeline chunk |

All required passages had been retrieved. The first six cases were rejected by
the combined condition that every hypothesis reference must be both retrieved
and quoted in historical findings. The saved baseline does not retain rejected
raw drafts, so it is not possible to identify every offending ID or prove which
side of that combined condition failed. This uncertainty is not replaced with
a fabricated detailed diagnosis. S05's saved errors identify the mismatched
public chunk (`PUB-132729161ab7:chunk:008`).

The structural problems were independently generated historical/hypothesis
references, requiring hypotheses even for factual questions, free-form copying
of long public quotations, and recovering labeled fixes only after validation.
The accepted C03 report also reversed which DNS server restarted, demonstrating
that exact quote/source membership alone cannot guarantee interpretation.

## Implemented approach

1. `evidence_catalog.py` extracts exact source spans with runtime-local fact IDs,
   real retrieved chunk IDs, offsets, kinds, and extraction provenance.
2. Synthetic causes, resolutions, and symptoms come from their labeled fields.
   Public prose uses bounded complete sentence spans; explicit causal/action
   markers help categorize them. Negated/qualified/rhetorical statements remain
   observations. This conservative rule set is not a general entailment engine.
3. The evidence gate selects catalog IDs. Generation selects finding IDs and
   optionally up to three root-cause fact IDs; it cannot author quotations,
   metadata, causal paraphrases, or new current-incident claims.
4. Python resolves those IDs to exact source text. Selected synthetic field pairs
   restore documented causes/resolutions before citation validation. No fixes
   are invented for missing fields.
5. A hypothesis must already reference a selected validated cause. It uses a
   fixed unconfirmed template preserving the exact historical mechanism, including
   actors and negation. Diagnostic guidance asks engineers to compare current
   evidence; it is not a claim of a confirmed cause or a historical fix.
6. Span, source-field, ID membership, and hypothesis-rendering checks augment the
   existing exact-quote and citation checks. Invalid selections fail closed;
   they are not silently dropped, fuzzily matched, or automatically retried.
7. Factual answers can have no current hypotheses. Missing or invalid evidence
   still produces the existing insufficient-evidence report.

The architecture deliberately trades free-form generated causal interpretation
for extractive evidence selection. It does not simply adjust a score threshold
to accept previously invalid drafts. Retrieval, MiniLM, models, context/output
settings, Mem0-disabled mode, and session-only Streamlit conversations are unchanged.

## Offline verification

- **81 regression tests passed:** existing 69 tests plus 12 targeted reliability
  tests. Existing generation fixtures were adapted to the new selection schema;
  malformed output, unknown citations, source-quote checks, and fallback coverage
  remain exercised.
- Added tests for unknown/unaligned IDs, resolution recovery, invented quotations,
  reversed DNS actors, source-field kind mismatch, negated public causes, missing
  evidence, malformed/unsupported prose, factual answers without hypotheses,
  dynamic allowed-ID schemas, and tampered offsets.
- All **17/17** baseline required reference excerpts remain available in catalogs.
  This is an offline availability check, not an acceptance/accuracy result.
- Protected baseline/source/configuration/environment/Mem0-ledger hashes match.
- No live Ollama, Pinecone, Mem0, or judge-model calls were needed for these checks.


## Before-and-after evaluation

| Measure | Original baseline | Phase 9 |
| --- | --- | --- |
| Accepted answerable reports | 5/12 | 10/12 |
| False refusals | 7/12 | 2/12 |
| Historical citation provenance | 16/16 | 45/45 |
| Supported exposed historical claims/hypotheses | 24/25 | 44/46 |
| Correct insufficient responses | 4/4 | 4/4 |
| Overall expected behavior | 8/16 | 13/16 |
| Actual local chat requests | 28 | 26 (cap 32) |
| Total generation-stage seconds | 732.973 | 408.022 |
| Mean answerable response seconds | 55.419 | 26.658 |

Both runs reused the same cached retrieval. No new Pinecone, Mem0, or judge-model calls were made. Existing model configuration and citation rules were retained, with stronger span/selection checks. Hypotheses are now extractive templates rather than free-form causal paraphrases; support scores therefore compare different output expressiveness, not pure model intelligence.

## Per-question review and remaining failures

| ID | Phase 9 status | Seconds | Expected behavior | Review |
| --- | --- | --- | --- | --- |
| E01 | investigation | 15.168 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| E02 | investigation | 21.717 | pass | Requested historical evidence and fixes are present with source-backed quotations. Extra separately labeled public incidents are beyond the requested target and can distract. |
| E03 | investigation | 20.998 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| E04 | investigation | 44.367 | pass | Requested historical evidence and fixes are present with source-backed quotations. Extra separately labeled public incidents are beyond the requested target and can distract. |
| S01 | investigation | 30.089 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| S02 | investigation | 46.925 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| S03 | investigation | 37.457 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| S04 | investigation | 11.684 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| S05 | investigation | 41.914 | fail | Core Workers KV causal evidence is present, but two background/prevention passages are wrongly typed as incident root causes; not a fully supported answer. |
| C01 | insufficient_evidence | 8.922 | fail | False refusal at evidence assessment; generic saved error does not distinguish malformed structure from transport failure. |
| C02 | investigation | 14.236 | pass | Requested historical evidence and fixes are present with source-backed quotations. |
| C03 | insufficient_evidence | 26.421 | fail | False refusal: evidence selection returned insufficient despite both required incidents being retrieved. |
| I01 | insufficient_evidence | 23.216 | pass | Correct insufficient-evidence fallback with no fabricated requested facts. |
| I02 | insufficient_evidence | 21.149 | pass | Correct insufficient-evidence fallback with no fabricated requested facts. |
| I03 | insufficient_evidence | 17.260 | pass | Correct insufficient-evidence fallback with no fabricated requested facts. |
| I04 | insufficient_evidence | 26.290 | pass | Correct insufficient-evidence fallback with no fabricated requested facts. |

## Interpretation and limitations

Coding-assistant qualitative review against retrieved source excerpts. Not independent human adjudication; exact quotes are not automatic semantic support.

Exact excerpts prevent invented quotes and actor/negation rewrites, but they do not prove that the selected fact answers the question. Public prose categorization uses conservative markers and is not a semantic entailment model. Additional unrequested sources, duplicate facts, incomplete answers, or fact-kind ambiguity remain possible. Generic diagnostic guidance is less tailored than the former free-form output.

The same development set informed this redesign. These before/after results are not independently blinded or held-out production accuracy. No production inference was changed during the re-evaluation. All invalid selections still fail closed; no fuzzy quote matching or acceptance threshold relaxation was introduced.

## Verification and files

**81 regression tests passed** (69 prior tests with schema fixtures adapted, plus 12 new reliability tests). `pip check` found no broken requirements. Protected baseline, source, embedding, environment, and Mem0-ledger hashes are checked separately in `verification_summary.json`. The Streamlit interface and session-only behavior are unchanged and covered by the regression suite.

Runtime changes: `src/incident_investigator/evidence_catalog.py` and `investigation.py`. Tests: `test_reliability.py`, updated generation fixtures in `test_investigation.py`, and one archived fake-memory fixture. New tooling: `scripts/evaluate_phase9.py`, `scripts/report_phase9.py`. New report/review: this file and `evaluation/phase9_answer_reviews.json`. README/architecture documentation describes the active behavior. Baseline artifacts were not overwritten.

Raw results and call accounting: `data/processed/phase9/generation.json`, `chat_requests.json`, `comparison_metrics.json`, `regression_tests.txt`. Source references were selected only from runtime retrieval; there are no evaluation IDs or prewritten question answers in the generation code.
