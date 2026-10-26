> PUBLICATION COPY: explanatory wording may be paraphrased; historical measurements are unchanged. The original local artifact is preserved and excluded from Git. Links to `evaluation/questions.json` identify the original evaluated dataset, which is not distributed. `questions.json` beside this file is an unevaluated summary inventory.

# Gen Academy Week 2 — RAG Evaluation Report

**Status: retrieval, approved generation, and coding-assistant qualitative review complete. Independent human review was not performed.**

## Application and dataset

34 incident reports (20 synthetic, 14 public), 104 chunks and cached 768-dimensional EmbeddingGemma vectors. Existing Pinecone Documents API hybrid search, RRF and local MiniLM were evaluated unchanged. Qwen generation was evaluated using the saved retrieval results. Mem0 is disabled and excluded; session-only conversations are unchanged.

16 questions: 4 exact, 5 semantic, 3 cross-document, 4 insufficient-evidence. Reference judgments are corpus-derived, not independently blinded. See `evaluation/questions.json` and `evaluation/PLAN.md`.

## The 16 evaluation questions

| ID | Category | Question | Required reference incidents |
| --- | --- | --- | --- |
| E01 | exact | What documented root cause and resolution explain Payments API HTTP 503 responses with elevated DB connections? | SYN-001 |
| E02 | exact | What caused Billing Service HTTP 500 errors immediately after release, and what was the recorded fix? | SYN-013 |
| E03 | exact | Why did Catalog Frontend static assets return 404 after deployment, and how was it resolved? | SYN-014 |
| E04 | exact | In GitHub DNS Outage Post Mortem, how long was the initial service downtime and the additional downtime for some repositories? | PUB-539796025e31 |
| S01 | semantic | Customers cannot finish checkout because one write waits behind another transaction. Which historical incident and remedy fit? | SYN-002 |
| S02 | semantic | Reads became much slower after a database schema update; the engine scans entire tables. What past explanation and fix are documented? | SYN-003 |
| S03 | semantic | A message is delivered again and customers receive the same email twice. What previous defect and corrective action match? | SYN-007 |
| S04 | semantic | Scheduled reports stopped appearing after a settings change moved execution away from universal time. What historical cause and recovery match? | SYN-015 |
| S05 | semantic | Which Cloudflare report explains how a shared central storage failure broke Workers KV cold reads and writes and cascaded to dependent services? | PUB-132729161ab7 |
| C01 | cross_document | Compare the historical HTTP 503 causes in Payments API, Checkout Gateway, and User Profile API. What different checks and fixes do they suggest? | SYN-001, SYN-005, SYN-006 |
| C02 | cross_document | Compare the TLS failure in Partner API Integration, login failure in Employee SSO, and repeated 401 errors in Mobile Application. How do the causes differ? | SYN-018, SYN-019, SYN-020 |
| C03 | cross_document | Compare the synthetic Public API Edge missing-DNS-record incident with GitHub DNS Outage Post Mortem. What configuration failures caused name-resolution trouble? | SYN-016, PUB-539796025e31 |
| I01 | insufficient | What is the documented root cause and repair procedure for quantum processor decoherence after a helium purge? | No supported answer expected |
| I02 | insufficient | Which CVE and attacker IP caused our payment outage yesterday? No security logs or forensic evidence are available. | No supported answer expected |
| I03 | insufficient | What exact database pool numeric value and production hostname must I change now to guarantee fixing our current HTTP 503 outage? No current configuration or logs are supplied. | No supported answer expected |
| I04 | insufficient | Does the available corpus document a satellite radiation hardware fault, including vendor-specific component replacement steps? | No supported answer expected |

## Actual retrieval results

Positive metrics use the 12 answerable questions; four insufficient cases have no positive retrieval labels. Retrieval errors count as misses. Strict precision uses only curated reference passages, so relevant unlabeled passages can be penalized.

| Metric | Actual value |
| --- | --- |
| required_evidence_recall_at_5 | 1.0000 |
| hit_at_5 | 1.0000 |
| reciprocal_rank_at_5 | 1.0000 |
| strict_judged_precision_at_5 | 0.2833 |
| all_required_evidence_found | 1.0000 |

Elapsed retrieval-run time: **31.083 seconds**. Errors: **0**; degraded questions: **0**; reranking active: **16/16**; metadata/text errors: **0**. These are observed outputs, not billing measurements.

| Category | Questions | Required-evidence recall@5 | MRR@5 | Complete-evidence rate |
| --- | --- | --- | --- | --- |
| exact | 4 | 1.0000 | 1.0000 | 1.0000 |
| semantic | 5 | 1.0000 | 1.0000 | 1.0000 |
| cross_document | 3 | 1.0000 | 1.0000 | 1.0000 |

## Per-question results and failure analysis

| ID | Category | Top five incidents in rank order | Required evidence missed | Seconds |
| --- | --- | --- | --- | --- |
| E01 | exact | SYN-001, SYN-006, SYN-005, SYN-008, SYN-003 | none | 8.392 |
| E02 | exact | SYN-013, PUB-923ebca890c0, SYN-005, PUB-3557997fc8b2, SYN-001 | none | 1.622 |
| E03 | exact | SYN-014, PUB-132729161ab7, PUB-3557997fc8b2, PUB-539796025e31, SYN-005 | none | 1.555 |
| E04 | exact | PUB-539796025e31, PUB-f3602faa9d13, PUB-539796025e31, PUB-f389f6f351e1, PUB-f3602faa9d13 | none | 1.593 |
| S01 | semantic | SYN-002, SYN-007, SYN-005, PUB-923ebca890c0, PUB-923ebca890c0 | none | 1.583 |
| S02 | semantic | SYN-003, PUB-0fbaebe05b3f, PUB-f3602faa9d13, PUB-0fbaebe05b3f, PUB-c7e282c7cab3 | none | 1.558 |
| S03 | semantic | SYN-007, PUB-3557997fc8b2, PUB-0fbaebe05b3f, PUB-539796025e31, PUB-f389f6f351e1 | none | 1.537 |
| S04 | semantic | SYN-015, SYN-004, PUB-bbd98be895de, SYN-003, SYN-017 | none | 1.362 |
| S05 | semantic | PUB-132729161ab7, PUB-132729161ab7, PUB-132729161ab7, PUB-132729161ab7, PUB-132729161ab7 | none | 1.498 |
| C01 | cross_document | SYN-005, SYN-006, SYN-001, SYN-008, SYN-002 | none | 1.509 |
| C02 | cross_document | SYN-018, SYN-019, PUB-132729161ab7, PUB-132729161ab7, SYN-020 | none | 1.524 |
| C03 | cross_document | SYN-016, PUB-539796025e31, PUB-539796025e31, PUB-74e36f9a604c, PUB-f3602faa9d13 | none | 1.365 |
| I01 | insufficient | PUB-c7e282c7cab3, PUB-c7e282c7cab3, PUB-bbd98be895de, PUB-539796025e31, PUB-132729161ab7 | Not applicable: answer abstention pending | 1.358 |
| I02 | insufficient | PUB-923ebca890c0, SYN-001, PUB-132729161ab7, PUB-0fbaebe05b3f, PUB-0fbaebe05b3f | Not applicable: answer abstention pending | 1.726 |
| I03 | insufficient | PUB-c7e282c7cab3, SYN-001, SYN-006, PUB-0fbaebe05b3f, PUB-0fbaebe05b3f | Not applicable: answer abstention pending | 1.437 |
| I04 | insufficient | PUB-74e36f9a604c, PUB-74e36f9a604c, PUB-132729161ab7, PUB-bbd98be895de, PUB-602939eef59b | Not applicable: answer abstention pending | 1.443 |

Misses below concern frozen required passages, not a universal judgment that all other returned material is irrelevant. No ranking parameters were tuned against this dataset.


Insufficient-evidence queries can still return nearest neighbors. Their existence does not demonstrate answerability or a model hallucination. Current-production values, attacker attribution, or unrelated domain facts must not be inferred from similar historical reports.

## Actual answer-quality results

| Measure | Actual numerator / denominator | Result |
| --- | --- | --- |
| Historical claim support (analyst review) | 16 / 16 | 100.00% |
| Hypothesis support (analyst review) | 8 / 9 | 88.89% |
| Automated citation provenance validity | 16 / 16 | 100.00% |
| Answerable response coverage | 5 / 12 | 41.67% |
| False-refusal rate | 7 / 12 | 58.33% |
| Safe insufficient-evidence handling | 4 / 4 | 100.00% |
| Insufficient status on negative questions | 4 / 4 | 100.00% |

Combined exposed-claim support (historical claims plus unconfirmed hypotheses): **24/25 (96.00%)**. This is coding-assistant review, not independent human adjudication.

Expected-behavior passes: **8/16**. Actual local chat requests: **28** (approved maximum 32); total generation-stage runtime: **732.973 seconds**. No additional retrieval or judge-model calls were used.

**Interpretation:** exposed-claim validity is conditional on fail-closed filtering; it does not count refused or empty answers as faithful successes. Response coverage and false refusals show the usability cost. Analyst support judgments were made by the coding assistant against saved passages, not by a blinded human reviewer or separate judge-model API.

| ID | Status | Generation-stage seconds | Expected behavior | Review / failure |
| --- | --- | --- | --- | --- |
| E01 | insufficient_evidence | 56.314 | fail | False refusal: required evidence was retrieved, but the draft was withheld because hypothesis citations were not validated in historical findings. |
| E02 | insufficient_evidence | 52.725 | fail | False refusal: required evidence was retrieved, but the draft was withheld because hypothesis citations were not validated in historical findings. |
| E03 | insufficient_evidence | 50.017 | fail | False refusal: required evidence was retrieved, but the draft was withheld because hypothesis citations were not validated in historical findings. |
| E04 | insufficient_evidence | 49.984 | fail | False refusal: required evidence was retrieved, but the draft was withheld because hypothesis citations were not validated in historical findings. |
| S01 | insufficient_evidence | 48.720 | fail | False refusal: required evidence was retrieved, but the draft was withheld because hypothesis citations were not validated in historical findings. |
| S02 | investigation | 49.577 | pass | Correct source root cause and documented resolution; plausible source-backed hypothesis is explicitly labeled unconfirmed. |
| S03 | investigation | 52.798 | pass | Correct source root cause and documented resolution; plausible source-backed hypothesis is explicitly labeled unconfirmed. Wording inside the S03 hypothesis says root cause involves, which is stronger than the surrounding uncertainty labels and merits future tightening. |
| S04 | investigation | 50.302 | pass | Correct UTC-to-local-time historical cause and timezone correction/backfill resolution; hypothesis explicitly unconfirmed with uncertainty about current applicability. |
| S05 | insufficient_evidence | 74.046 | fail | False refusal despite required public evidence: generated quotations did not occur in the cited Workers KV timeline passage; the validator withheld all findings. |
| C01 | insufficient_evidence | 63.700 | fail | False refusal of an answerable three-incident comparison: all three required chunks were retrieved, but a hypothesis referenced a passage not validated in historical findings. |
| C02 | investigation | 61.716 | pass | Correctly distinguishes missing intermediate certificate, stale issuer configuration, and client clock skew, with all three documented resolutions. Hypotheses are source-backed and labeled unconfirmed, although their inner wording involves is stronger than ideal. |
| C03 | investigation | 55.123 | fail | Partial comparison: source labels and four quoted historical claims are correct, but hypothesis 2 reverses the restart failure. The public source says the authoritative server restarted while the caching server did not; the answer hypothesizes that the authoritative server did not restart. The public documented root cause is not correctly stated as a historical finding. Hypotheses 1 and 3 are plausible source-anchored possibilities; hypothesis 1 is an inference, not a documented causal conclusion. |
| I01 | insufficient_evidence | 16.257 | pass | Correct abstention: no supported matching incident or requested current-specific facts established; no invented causes, CVEs, IPs, numeric settings, hostnames, guarantees, or hardware repair steps. Generic diagnostic advice is labeled as not retrieved evidence. |
| I02 | insufficient_evidence | 16.395 | pass | Correct abstention: no supported matching incident or requested current-specific facts established; no invented causes, CVEs, IPs, numeric settings, hostnames, guarantees, or hardware repair steps. Generic diagnostic advice is labeled as not retrieved evidence. |
| I03 | insufficient_evidence | 17.136 | pass | Correct abstention: no supported matching incident or requested current-specific facts established; no invented causes, CVEs, IPs, numeric settings, hostnames, guarantees, or hardware repair steps. Generic diagnostic advice is labeled as not retrieved evidence. |
| I04 | insufficient_evidence | 17.638 | pass | Correct abstention: no supported matching incident or requested current-specific facts established; no invented causes, CVEs, IPs, numeric settings, hostnames, guarantees, or hardware repair steps. Generic diagnostic advice is labeled as not retrieved evidence. |

### Failure analysis and next steps

Six answerable cases failed hypothesis-citation alignment (E01–E04, S01, C01); S05 failed exact quotation checks. C03 passed automated validation but contains a semantic error: it reverses which DNS server failed to restart. The source says the authoritative server restarted while the caching server did not, while the hypothesis says that server did not restart. S03/C02 also retain stronger-than-ideal wording inside otherwise unconfirmed hypotheses. These problems were not patched during the evaluation.

All positive reference units were retrieved, so missing required passages do not explain these particular answer failures. Rejected drafts and conservative abstentions are recorded individually above. No prompts, models, index settings, or citation rules were changed during this evaluation.

Safe future work: improve structured-output/citation-ID alignment, bound the number of hypotheses, and make the answer schema suitable for factual questions and cross-document comparisons. Preserve source-membership and exact-quote checks. Test changes against a separate held-out set; do not tune to these 16 questions and then describe the same scores as unbiased validation. These are recommendations, not implemented changes.

## Verification and limitations

Protected data/configuration/environment/ledger hashes unchanged: **True**. Pinecone operations were read-only. No Mem0 operations, model changes, schema changes, or source mutations were requested by the runner.

All **69 regression tests passed**, including the existing 65 and four evaluation-helper tests; `pip check` found no broken requirements. Detailed outcomes are in `regression_tests.txt` and the final verification summary. Prior sandbox network failures are archived separately and are not presented as ranking results.

This is a small, manually curated, corpus-specific test set with incomplete relevance labels. Synthetic incidents are fictional examples. Do not generalize these measurements to production accuracy, or treat this small completed run as comprehensive production validation.

Full generated outputs: `data/processed/evaluation/generation.json`; per-question review: `evaluation/answer_reviews.json`; metrics: `data/processed/evaluation/answer_metrics.json`.
