# Local GitHub publication preparation

**Status:** Local preparation only. No staging, commits, GitHub repository creation, push, visibility change or deployment has been performed. Proposed repository name: `ai-incident-root-cause-investigator`.

## What will be published

The exact list is [publication_manifest.txt](publication_manifest.txt). It includes source code, non-secret TOML settings, the empty environment template, tests, setup instructions, submission documentation and labeled evaluation publication copies. It excludes full public articles, all original evaluation artifacts, credentials, memories, logs, embeddings, model files and generated chunks. The manifest is a proposed upload list, not a record of an upload.

## Evaluation and source sharing

The original evaluated `evaluation/questions.json`, reports and review files remain unchanged locally. Git excludes the original files and includes only `evaluation/publication_safe/`.

The publication question inventory preserves question IDs, categories and wording, but replaces reference quotations and answer keys with concise original summaries and original-source links. It omits scoring evidence units, exact chunk labels and corpus-hash configuration. Its provenance includes the original dataset's SHA-256. It is explicitly **unevaluated** and cannot replace the original dataset in the scoring loader. Historical scores remain attributable only to the original version.

Publication copies of the historical reports/reviews retain numerical measurements. Brief excerpt fragments in explanatory commentary have been paraphrased. The reports' publisher links and the submission source inventory provide attribution. The original files and raw outputs remain local evidence; they are not silently rewritten to support the publication dataset.

A regression fixture formerly repeated a public DNS excerpt. It now uses clearly fictional lab-node prose while retaining the actor/negation validation test. This does not change citation safeguards or historical evaluation results.

Full public articles are not included and no permission to redistribute them is asserted. Short factual descriptions, source titles and links remain. Automated overlap checks are a technical precaution, not legal certification. Future article collection/sharing requires its own permissions review.

## Reproducibility

Follow [reproducing_sample.md](reproducing_sample.md). The existing generator creates 20 fictional reports without downloading articles or overwriting existing files. The new-clone ingestion produces 20 validated chunks. Local sample preparation does not create embeddings or contact Pinecone, Tavily, Ollama or Mem0.

The temporary checkout simulation copies only the proposed publication files, generates synthetic data, ingests and validates it, then runs the suite with network connections blocked. It contains no credentials, original incident corpus, vector cache or model weights. It reuses this machine's installed Python dependencies and a copied tokenizer vocabulary cache; it is not a clean dependency-installation or cross-platform compatibility test. A genuinely new environment needs dependency installation and may need a first-time tokenizer download.

Six artifact-dependent cases skip in this checkout: one original-evaluation check, one public-document check and four cached-vector checks. All remaining checks run using local synthetic data and mocked services. The keyword-search unit test now explicitly mocks its local-record boundary instead of relying on the author's embedding cache.

## Verification results

- Complete local suite: **86 tests passed** (the prior 83 plus three publication checks).
- Temporary synthetic-only checkout: **86 tests discovered; 80 passed and six explicitly skipped; no failures**.
- Sample ingestion validation: **20 incidents and 20 chunks checked; no validation errors**.
- Dependency consistency: `pip check` found no broken requirements.
- Original evaluation artifacts, incident JSON reports, cached embeddings and local `.env` are protected by before/after hash comparison.
- Publication candidates are checked for known credential formats, exact configured secret values, personal absolute paths and substantial verbatim source overlap. Findings and limits are described below.

The three publication tests check inventory/version separation, fictional generation without overwrite, and unchanged final review counts. They are software checks, not additional RAG quality measurements. The historical evaluation still reports 83 regression tests at that point in development; its artifacts are not updated to pretend publication checks existed then.

## Exclusions and portable documentation

`.gitignore` covers environment secrets, key material, local models and Ollama caches, Python environments/build caches, agent state, temporary logs, private memory data and all generated data under `data/`. Source/test fixtures and non-secret examples remain eligible.

Publication-facing instructions use the repository folder name and `python3.12`, rather than a personal Mac path or a downloaded interpreter's machine-specific path. Local environment configuration and application/model/index settings are unchanged.

## Final publication audit

The final manifest contains **77 files**, approximately **498 KB**, with no file over 1 MB. The scan found no recognized credential formats, no exact configured API-key values, no personal absolute paths, and no ten-word public-article overlaps after excluding source titles. No secret values are printed in these findings. The scan cannot establish the absence of all possible sensitive information or determine legal permissions.

All protected original evaluation artifacts, incident reports, embedding files and `.env` matched their pre-preparation hashes. Publication review JSON files preserve every historical numeric and Boolean value. Test logs are local preparation evidence, not new model response-time or RAG quality measurements.

## Remaining decisions before GitHub creation

- Approve the final manifest and choose repository visibility. No GitHub remote currently exists and no commit exists.
- Decide a code license; none has been added automatically. A code license cannot grant rights to third-party source reports or model weights.
- Supply author details, repository URL, demo video and screenshots for the submission.
- Accept that the published synthetic sample cannot independently reproduce the full-corpus historical evaluation. Full reproduction requires separately authorized source data and the original local evaluation artifacts.
- Some historical report references point to intentionally excluded local evidence files. These are provenance references, not promises that every local artifact is distributed.
- Secret scanning cannot guarantee detection of every possible secret. Publisher permissions are not established by an overlap scan. No deployment, authentication or production-readiness claim is made.

Stop here for explicit publication approval. Any later staging, commit, repository creation or push must use the reviewed manifest and the approved visibility.
