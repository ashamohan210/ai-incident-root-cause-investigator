# Gen Academy Week 2 submission checklist

Checked items below were verified from local code, configuration, and saved artifacts during documentation preparation. No new RAG evaluation, live service check, deployment, or publication was performed. Later local publication-preparation tests are reported separately in [publication_preparation.md](publication_preparation.md).

## Documentation prepared

- [x] [Main submission report](gen_academy_submission.md) contains the twelve requested sections, the six-field RAG framework, evaluation definitions, lessons and limitations.
- [x] [Architecture diagram](architecture_diagram.md) describes the active system and supplies Mermaid source.
- [x] Original and Phase 9 evaluation reports are cited separately; baseline results are not overwritten.
- [x] Active models and retrieval are accurately described; Nebius remains paused and Mem0 is excluded from the active stack.
- [x] Session-only conversations and the absence of deployment are stated explicitly.
- [x] Synthetic reports are labeled fictional; public-source attribution is included.
- [x] Evaluation results distinguish coverage, acceptance, provenance, qualitative support, abstention and regression tests.

## Verified saved results to use in submission

- [x] Original top-five required-reference coverage: 12/12 answerable questions; MRR@5 1.00.
- [x] Final Phase 9: 11/12 accepted answerable reports and 1/12 false refusals.
- [x] Final insufficient-evidence handling: 4/4 correct responses.
- [x] Final provenance: 45/45 valid checks; qualitative claim support: 42/45.
- [x] Final expected task behavior: 15/16; saved regression suite: 83 tests passed.
- [x] Small curated development set and non-independent coding-assistant review are disclosed.
- [x] Three unclear public fragments and the remaining C03 schema-limit refusal are disclosed. Do not claim faithfulness improved or all future hypotheses are validated by the live evaluation.

Sources: [baseline](../evaluation/publication_safe/REPORT.md), [final reliability report](../evaluation/publication_safe/PHASE9_REPORT.md), [final metrics](../data/processed/phase9/run2/comparison_metrics.json), [verification](../data/processed/phase9/verification_summary.json). These are historical saved outcomes, not tests rerun during Phase 10.

## Your input before submitting

- [ ] Add author name and any cohort or student details required by the Academy.
- [ ] Add the GitHub repository URL. Check repository visibility and reviewer access; no repository was created or published by this documentation step.
- [ ] Review tracked files for credentials, local environment files, logs, and private material before manually publishing. Never include API key values in the report, screenshots or video.
- [ ] Decide how reviewers can access authorized sample data or reproduce the project. Local data is excluded from Git; do not assume repository readers receive all local artifacts. Review public-source reuse rights before sharing full text.
- [ ] Record and link the five-minute demo video. Use a previously verified answerable example and an insufficient-evidence example; show real behavior, not a promised result.
- [ ] Add actual screenshots: homepage/session note; accepted report with citations and source-type labels; insufficient-evidence response. Optionally add the evaluation comparison.
- [ ] Render the Mermaid diagram to an image and insert it in Google Docs. Check legibility and captioning.
- [ ] Copy the rendered main document into Google Docs, apply heading styles, inspect tables and links, and remove every remaining placeholder.
- [ ] Confirm any additional Academy rubric, sharing-format, deadline, or prompt-log requirements; these have not been supplied here.
- [ ] If a full prompt log is required, export and review the actual development conversation. The report includes genuine excerpts, not an invented transcript.
- [ ] Review the final claims in your own words and ensure you can explain what each component does.

## Suggested five-minute demonstration outline

This is a recording plan, not an already completed video or measured benchmark.

- Introduce the engineer's problem and show the local homepage and session-only note.
- Explain the corpus and hybrid retrieval diagram briefly.
- Run an answerable investigation; use generation time to explain semantic/BM25 search and reranking. Inspect an incident ID, exact passage, and source reference.
- Show an insufficient-evidence example and explain why a similar incident does not prove a current cause.
- Present baseline versus Phase 9 results, the curated-set caveat, and remaining limitations.

A live investigation uses local Ollama and Pinecone reads; it should not use Mem0. Do not regenerate embeddings, modify the index, or rerun the full evaluation just to record the demo. Timing may vary.

## Local launch reference

From the VS Code terminal:

```bash
cd ai-incident-root-cause-investigator
source .venv/bin/activate
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`. Ollama and the existing configured Pinecone connection must be available for live investigations. Follow the existing [README](../README.md) for setup; never paste `.env` contents into the report. This launch command was documented, not executed during this documentation-only phase.
