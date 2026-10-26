# Reproduce the synthetic sample without hosted services

The published repository is source code, documentation, evaluation summaries, and tests. It does not contain the author's public-article corpus, embeddings, credentials, or private memories. No Pinecone account, Ollama model, Tavily key, or Mem0 key is needed for synthetic generation, local ingestion, mocked tests, or opening the homepage.

## Setup from a new clone

Install Python 3.12 and open the repository folder in a terminal. On macOS/Linux:

```bash
cd ai-incident-root-cause-investigator
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python phase2_incident_dataset.py all
python scripts/ingest_incidents.py
python scripts/validate_chunks.py
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell and use your Python 3.12 executable to create the environment.

The existing generator produces 20 explicitly fictional reports. It keeps any existing report rather than overwriting it. Run these steps in a new clone to obtain a synthetic-only knowledge base. Ingestion processes reports already present; it never fetches public articles. Outputs remain excluded from Git. Collection timestamps can differ between runs; byte-identical copies of the historical evaluated corpus are not promised.

Dependency installation needs internet. On the first ingestion, tiktoken may download its tokenizer vocabulary, then cache it locally. This is a tokenizer download, not a paid inference or collection call. Once dependencies and vocabulary are cached, these steps need no external service. Do not run public collection, embedding, indexing, or full generation-evaluation commands as part of this quickstart.

## What works in the synthetic-only checkout

- The generator and LangChain ingestion/validation create a traceable local sample.
- The offline regression suite uses fake LLM, Pinecone, reranker, collector and memory boundaries. Generated synthetic data is needed by ingestion and cache tests, so run setup first.
- Streamlit can display its homepage. Automated UI tests exercise successful submissions using mocked backends.
- Actual interactive investigations require separately configured Ollama models and an authorized Pinecone knowledge base. The sample setup does not upload anything or connect to the author's database.

## Checks that require the original local knowledge base

Six existing regression cases skip with explicit reasons when their artifacts are absent:

1. Frozen evaluation/reference-quote validation requires the original `evaluation/questions.json` and its matching full corpus.
2. Public JSON/source-metadata validation requires independently obtained public fixtures.
3. Four Pinecone payload/identity/upload/search cases require the original cached embedding snapshot. Their remote clients are mocked, so they still do not need live credentials.

Other retrieval, fusion, citation, structured-output, disabled-memory and UI tests remain runnable. A skipped check is not a pass and does not verify the original evaluated corpus. The complete original local suite is also run separately during publication preparation.

## Evaluation provenance

`evaluation/publication_safe/questions.json` is a readable, **unevaluated** question inventory. Public quotations, verbatim answer keys, gold chunk labels and corpus-hash scoring configuration are not distributed. It is intentionally incompatible with the exact-quote evaluation loader; do not substitute it for the frozen dataset or claim the historical scores were measured on it.

Publication copies of historical reports and reviews retain numerical results. Some explanatory wording is paraphrased. Original evaluated questions, reports, reviews and raw outputs remain unchanged locally and are excluded from Git. The reports are historical evidence of the project run, not results reproducible from the smaller synthetic sample alone.

Source links identify the original publishers. No full public article, local investigation output, hosted-memory record, vector cache or API key is included. Recollecting or redistributing public content requires a separate review of publisher permissions; this sample workflow does not perform collection.
