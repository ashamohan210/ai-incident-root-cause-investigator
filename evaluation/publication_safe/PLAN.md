> PUBLICATION COPY: explanatory wording may be paraphrased; historical measurements are unchanged. The original local artifact is preserved and excluded from Git. Links to `evaluation/questions.json` identify the original evaluated dataset, which is not distributed. `questions.json` beside this file is an unevaluated summary inventory.

# Week 2 RAG evaluation plan

## Active configuration and boundaries

Evaluate the current 34-incident/104-chunk corpus, Ollama `embeddinggemma:300m`
(768 dimensions), Pinecone `incident-rca` / `historical-incidents`, existing
semantic + BM25 retrieval, RRF, local MiniLM, and LangGraph with local
`qwen3.5:4b`. Mem0 is disabled and excluded. Session-only Streamlit conversations
are preserved; each evaluation question is independent, without chat history.
No index/schema changes, document edits, re-embedding, model changes, or citation
rule changes are part of evaluation.

## Final question set

`questions.json` contains 16 corpus-derived questions:

| Category | Count | Purpose |
| --- | --- | --- |
| Exact technical match | 4 | Error signatures, named services, and a documented public-outage duration |
| Semantic similarity | 5 | Paraphrased symptoms/dependencies, including a public postmortem |
| Cross-document | 3 | Distinguish several causes or compare synthetic and public incidents |
| Insufficient evidence | 4 | Unsupported domains and missing current-incident/forensic details |

Positive questions include reference incident/chunk IDs, verbatim support,
source types/paths/URLs, expected behavior, and documented synthetic resolutions.
Negative questions have no positive evidence labels and require withholding
unsupported requested facts. Existing similar passages do not establish an exact
production hostname, pool value, attacker, or CVE. Labels were curated from this
corpus, not independently blinded, and are not exhaustive relevance judgments.
Corpus SHA-256 and question-set hashes bind results to the frozen data.

## Stage 1: retrieval only

Run existing `hybrid_search` unchanged once per question. Planned high-level
calls: 16 local query-embedding requests, 32 Pinecone search invocations (semantic
and keyword), and 16 local reranking invocations. No chat generation or LLM judge;
no Tavily collection or Mem0 calls. Actual HTTP attempts/credits are not metered
by this runner, so planned counts must not be presented as billing measurements.
Existing document embeddings are reused.

For the 12 answerable questions, report:

- Required-evidence recall@5: fraction of required reference units present in top 5.
- Hit@5: at least one reference passage appears.
- MRR@5: reciprocal rank of the first reference passage, or zero if none appears.
- Strict judged precision@5: reference-labeled passages returned divided by five.
  Unlabeled passages can still be relevant; this is not exhaustive precision.
- Complete-evidence rate: all required reference units present, particularly
  important for cross-document questions.

For all 16: record returned IDs/scores/text/source metadata, phase latency,
reranker activation, errors/warnings, duplicate IDs, and exact local metadata/text
agreement. Four insufficient cases are excluded from positive retrieval means.
Do not score irrelevant nearest neighbors as an answer or an abstention: retrieval
alone cannot measure answer faithfulness, generated citations, or refusal behavior.
Record environment failures separately from ranking failures.

## Stage 2: generation — explicit approval required

Reuse the saved retrieval results through the existing graph's injectable
retriever. No new Pinecone requests or query embeddings are necessary. No
persistent memory or session history is supplied. Run 16 questions once each.

The current graph makes at most two `generate` requests per question: evidence
assessment and structured answer generation. Maximum **32 local chat model
calls**, typically fewer because lexical/evidence gates can abstain early.
No automatic retries and no LLM-as-judge calls. Existing model options remain:
8192 context tokens, 1800 output-token cap, 180-second timeout per request.
Expected wall time: **15–25 minutes**, based on prior approximately 63–73-second
accepted investigations and cheaper early abstentions. This is an estimate,
not a guarantee; a pathological 32-request timeout run could approach 96 minutes
plus overhead. Report actual request counts and elapsed times after execution.
Do not execute this stage until the user approves this call/runtime plan.

## Answer scoring after generation

Review in this run is a qualitative review by the coding assistant, with explicit
per-question reasons and denominators. It is not independent human adjudication,
not a separate judge-model API call, and not a production ground-truth guarantee.

1. **Faithfulness:** analyst-review each atomic historical claim and current
   hypothesis against retrieved evidence. Record supported / unsupported / unclear
   with reasons. Report supported claims / reviewed claims and all denominators.
   A verbatim quote is not proof that its assigned causal meaning is correct.
2. **Citation correctness:** automated source-membership, exact-quote, metadata,
   and uncertainty audits; additionally inspect claim-to-passage entailment.
   Report citation validity and answer coverage separately so empty answers cannot
   appear perfectly faithful. Cite only retrieved documents, never user context.
3. **Expected-answer coverage:** compare against required reference units and
   documented fixes. Record absent causes/resolutions or partial comparisons.
4. **Insufficient evidence:** for four negatives, measure whether unsupported
   requested facts were withheld with a clear limitation. `insufficient_evidence`
   status is an automated proxy, not sufficient by itself: cautious historical
   guidance can be acceptable if the requested unknown facts are explicitly
   withheld. Report false refusals among the 12 answerable questions separately.
5. Capture invalid JSON, rejected drafts, wrong certainty, service errors,
   incomplete cross-document coverage, and latency. Never turn rejected drafts
   or unreviewed outputs into passing faithfulness scores.

## Reproduction

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python scripts/evaluate_rag.py retrieval
```

The retrieval run is already saved and the runner refuses to overwrite or silently
repeat started runs. Review artifacts before another authorized run. After explicit
approval only, the prepared generation command is:

```bash
python scripts/evaluate_rag.py generation --approve-llm
```

The approval flag is not permission by itself. If interrupted, inspect saved
progress rather than automatically retrying. All local raw outputs are under
`data/processed/evaluation/` (ignored by Git). The earlier sandbox-blocked attempt
is retained separately under `data/processed/evaluation_sandbox_blocked/`.

The Gen Academy report must distinguish completed retrieval results from pending
answer evaluation. No answer metrics are to be invented before the generation
and review stages are complete.
