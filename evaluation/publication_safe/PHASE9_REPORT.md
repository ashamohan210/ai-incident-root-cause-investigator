> PUBLICATION COPY: explanatory wording may be paraphrased; historical measurements are unchanged. The original local artifact is preserved and excluded from Git. Links to `evaluation/questions.json` identify the original evaluated dataset, which is not distributed. `questions.json` beside this file is an unevaluated summary inventory.

# Phase 9 — Investigation reliability improvements

**Status: safer-revision implementation, offline tests, separately approved re-evaluation, and coding-assistant review complete.**

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
   The first experiment used public causal/action markers as role labels and
   misclassified two passages. The current revision uses markers for salience
   only: all untyped public prose remains verbatim observations. It does not
   infer root-cause/resolution fields or current hypotheses from untyped prose.
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

- **83 regression tests passed:** existing 69 tests plus 14 targeted reliability
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
| Accepted answerable reports | 5/12 | 11/12 |
| False refusals | 7/12 | 1/12 |
| Historical citation provenance | 16/16 | 45/45 |
| Supported exposed historical claims/hypotheses | 24/25 | 42/45 |
| Correct insufficient responses | 4/4 | 4/4 |
| Overall expected behavior | 8/16 | 15/16 |
| Actual local chat requests | 28 | 28 (cap 32) |
| Total generation-stage seconds | 732.973 | 588.817 |
| Mean answerable response seconds | 55.419 | 39.389 |

Both runs reused the same cached retrieval. No new Pinecone, Mem0, or judge-model calls were made. Existing model configuration and citation rules were retained, with stronger span/selection checks. Hypotheses are now extractive templates rather than free-form causal paraphrases; support scores therefore compare different output expressiveness, not pure model intelligence.

## Per-question review and remaining failures

| ID | Phase 9 status | Seconds | Expected behavior | Review |
| --- | --- | --- | --- | --- |
| E01 | investigation | 17.942 | pass | Correct Payments API pool-capacity cause and documented controlled rollout fix, copied from labeled fields. |
| E02 | investigation | 28.688 | pass | Correct Billing configuration-key cause and rollback/re-release resolution; no unrelated public causes selected. |
| E03 | investigation | 28.449 | pass | Correct manifest/CDN mismatch and matching-bundle/cache-invalidation fix. |
| E04 | investigation | 45.922 | pass | Both requested downtime durations are correctly quoted from the public GitHub report; duplicate clipped introduction adds noise but the complete duration sentence is present. |
| S01 | investigation | 45.065 | pass | Correct blocking-transaction cause and reviewed termination/shorter-scope resolution. |
| S02 | investigation | 55.660 | pass | Correct missing-index/table-scan cause and online-index/query-plan verification resolution. |
| S03 | investigation | 60.699 | pass | Correct non-idempotent retry/redelivery cause and idempotency-key resolution; no definite current-cause paraphrase. |
| S04 | investigation | 19.122 | pass | Correct UTC/local-time change and correction/backfill resolution. |
| S05 | investigation | 59.624 | pass | Core central-storage/Workers KV cascade evidence is correctly quoted as public observations, not inferred role labels. One extra fragment (an impact fragment without an identified subject) has no subject and is counted unclear, not supported. |
| C01 | investigation | 21.022 | pass | All three requested HTTP 503 mechanisms and documented fixes are present with distinct incident references. |
| C02 | investigation | 20.901 | pass | All three requested synthetic causes and fixes are correctly distinguished. Extra Cloudflare material is unrequested; two clipped continuation fragments are counted unclear rather than supported. |
| C03 | insufficient_evidence | 69.573 | fail | False refusal: raw response contains 40 finding IDs against the maximum 20. Structured validation rejected it; no silent truncation, retries, or changed limits. |
| I01 | insufficient_evidence | 30.120 | pass | Correct insufficient-evidence fallback; no fabricated domain facts, attacker/CVE attribution, numeric settings, hostnames, or guaranteed repairs. |
| I02 | insufficient_evidence | 29.887 | pass | Correct insufficient-evidence fallback; no fabricated domain facts, attacker/CVE attribution, numeric settings, hostnames, or guaranteed repairs. |
| I03 | insufficient_evidence | 26.883 | pass | Correct insufficient-evidence fallback; no fabricated domain facts, attacker/CVE attribution, numeric settings, hostnames, or guaranteed repairs. |
| I04 | insufficient_evidence | 29.049 | pass | Correct insufficient-evidence fallback; no fabricated domain facts, attacker/CVE attribution, numeric settings, hostnames, or guaranteed repairs. |

## Preserved first experiment

The first separately approved run used **26** chat calls in **408.022 seconds**. It accepted **10/12** answerable cases, but review found **2 unsupported public root-cause labels**. Those results were not treated as a successful release. The safer revision removes automatic role labeling of public prose and adds source titles. First-run report/reviews/raw outputs remain intact.

Across the two separately approved runs, actual chat requests total **54**. Each approval capped its run at 32; no retries or additional retrieval were used.

## Interpretation and limitations

Coding-assistant qualitative inspection against full retrieved passages, not independent human adjudication or a judge-model API. Unclear fragments are not counted as supported. Expected-behavior passes measure correct task evidence and abstention; they do not imply every auxiliary excerpt is clear. No current hypotheses were selected in this factual/comparison evaluation set.

Strict exposed-claim support is **42/45**, compared with baseline 24/25. The revised run has **3 unclear public fragments**, not counted as supported, and **0 identified source contradictions**. Thus acceptance improved, but a faithfulness improvement must not be claimed. All current-hypothesis lists were empty in this factual/comparison set, so live hypothesis support is not measurable in this run. Offline mechanism tests cover actor/negation preservation.

Exact excerpts prevent invented quotes and actor/negation rewrites, but they do not prove that the selected fact answers the question. Public prose stays as neutral observations; no automatic public causal/resolution classification is asserted. Markers affect excerpt salience only. Additional unrequested sources, duplicate facts, incomplete answers, or fact-kind ambiguity remain possible. Generic diagnostic guidance is less tailored than the former free-form output.

The same development set informed this redesign. These before/after results are not independently blinded or held-out production accuracy. No production inference was changed during the re-evaluation. All invalid selections still fail closed; no fuzzy quote matching or acceptance threshold relaxation was introduced.

## Verification and files

**83 regression tests passed** (69 prior tests with schema fixtures adapted, plus 14 new reliability tests). `pip check` found no broken requirements. Protected baseline, source, embedding, environment, and Mem0-ledger hashes are checked separately in `verification_summary.json`. The Streamlit interface and session-only behavior are unchanged and covered by the regression suite.

Runtime changes: `src/incident_investigator/evidence_catalog.py` and `investigation.py`. Tests: `test_reliability.py`, updated generation fixtures in `test_investigation.py`, and one archived fake-memory fixture. New tooling: `scripts/evaluate_phase9.py`, `scripts/report_phase9.py`. New report/review: this file and `evaluation/phase9_answer_reviews.json`. README/architecture documentation describes the active behavior. Baseline artifacts were not overwritten.

Raw results and call accounting: `data/processed/phase9/run2/generation.json`, `chat_requests.json`, `comparison_metrics.json`; offline tests are in `data/processed/phase9/regression_tests.txt`. The first experiment remains under the parent directory and in `PHASE9_RUN1_REPORT.md`. Source references were selected only from runtime retrieval; there are no evaluation IDs or prewritten question answers in the generation code.
