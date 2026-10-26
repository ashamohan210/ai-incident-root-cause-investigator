# Project architecture

## Current Week 2 architecture — memory disabled

Streamlit forms call the existing memory-free LangGraph investigation path:
`analyze → retrieve → check_evidence → generate / insufficient_evidence → validate_citations`.
Pinecone Documents API supplies semantic/BM25 passages; RRF and local MiniLM
rank them. Local Ollama `qwen3.5:4b` generates structured drafts, with unchanged
quotation and citation validation. The existing 104 vectors still use Ollama
`embeddinggemma:300m`; no embedding, model, index, or ranking changes were made.

Follow-ups use bounded user-written context from `st.session_state` (initial
incident plus recent questions). User context is untrusted, not documentary
evidence; generated assistant hypotheses are not replayed as facts. Conversation
history may disappear on reload or session end. Investigation IDs partition
local workspaces; retaining an ID in the URL does not restore history.

Mem0 is an optional future enhancement, **not part of the active Week 2 stack**.
`config/memory.toml` has `enabled = false`. The graph ignores supplied memory
scopes/adapters when disabled; the client factory, adapter operations, and HTTP
request hook all block hosted calls. The UI has no Mem0 imports or persistent
resume/save controls. Existing remote memories and the local key are untouched.

Nebius remains paused. The separate Week 2 evaluation uses frozen corpus-grounded
questions and a staged retrieval / approved-generation runner. It injects saved
retrieval results into the existing graph rather than modifying runtime retrieval
or citation checks. Mem0 and conversation history are excluded. No deployment
was added. Older phase records below are historical, not active capabilities.

## Earlier Phase 2B–4 design record

The following records preserve the earlier implementation sequence; current
capabilities are described above and in the later Phase 5–8 sections.

The 20 synthetic reports and 14 reviewed public reports feed the LangChain loader,
which writes 104 chunks to `data/processed/chunks.jsonl`. The embedding refresh
reads those chunks directly and reuses compatible vectors based on content and
model/configuration fingerprints. Original synthetic reports remain unchanged.

`config/providers.toml` separates provider choices from processing code:

| Responsibility | Choice | Current status |
| --- | --- | --- |
| Embeddings | Ollama / EmbeddingGemma 300M | Local adapter and verification CLI |
| Future LLM generation | Ollama | Configurable selection; no generation implementation |
| Future cloud models | Nebius | Paused; no credentials read or calls made |
| Public postmortem collection | Tavily | Bounded SDK collector; approved run completed |
| Persistent investigation memory | Mem0 Platform | Retained in plan; not connected |
| Vector storage | Pinecone | Planned; creation requires user approval |

The embedding provider exposes `embed_documents` and `embed_query`. Future
providers can implement that interface without changing the dataset. An LLM
protocol establishes a separate future boundary: embedding models turn text into
numbers, while LLMs generate text. Selecting an unimplemented provider fails
explicitly, rather than silently falling back to another service.

Settings use standard-library TOML support and exported environment overrides;
the current local increment does not load `.env` or require credentials. Keep
the local `.env` private for future integrations. LLM model selection remains
blank until a generation phase is requested.

The Ollama adapter calls `/api/version`, `/api/tags`, and `/api/embed` on localhost
only. It uses EmbeddingGemma retrieval prefixes for documents and queries and
sets `truncate=false` so oversized inputs fail rather than silently lose text.
It rejects empty, zero, non-finite, mismatched-count, or mixed-dimension vectors.

Verification saves vectors, chunk IDs, metadata, original text, model digest,
and measured dimensions under `data/local_embeddings/`, separate from Phase 3.
This is a local artifact, not an upload or vector database. A different embedding
model or task format requires re-embedding the entire collection: equal vector
dimensions do not mean different models are compatible.

Before Pinecone work resumes, inspect SDK/API compatibility and the existing
index, then propose the measured dimension, cosine metric, `incident-rca` index,
and `historical-incidents` namespace. Ask the user before creating an index.
No Pinecone dimension or external resource is configured by this increment.

No reranking, BM25, LangGraph, answer generation, or formal evaluation is added.

The public collection SDK reads only TAVILY_API_KEY through python-dotenv; it
does not activate other credentials. Per-run limits are 7 basic Search requests,
6 basic Extract requests (at most 5 URLs each), and 13 conservatively reserved
credits. Requests are journaled before transmission; no automatic retries run.
An existing journal blocks a repeat paid run. Actual API usage is saved separately
from reservations. The completed run reported 11 credits across 12 requests.

Public records are built offline from a reviewed primary-source allowlist.
Duplicate aliases and non-incident pages are excluded. Structured facts use
verbatim mapped sections and explicit nulls; full cleaned narratives remain
traceable to original URLs. Categories are analyst labels. Sources remain local
and private; no redistribution permission is asserted. The original Phase 3
snapshots and synthetic fingerprints are retained for preservation checks.

## Phase 5 retrieval

Semantic-only search is preserved. Hybrid retrieval performs separate read-only
Documents API searches with DenseVectorQuery and verified TextQuery/BM25 over
chunk_text. Each branch returns up to 10 results. Client-side RRF (k=60) merges
ranks, deduplicates by stable chunk ID, and keeps at most 10 candidates. An
optional offline CPU cross-encoder reranks those candidates and returns five.
Unavailable local reranking retains RRF ordering with an explicit status. The
MiniLM reranker was installed and verified active on the 16 GB Apple Silicon Mac.
Source metadata and passages remain attached throughout. No Pinecone schema or
stored vector changes occur. Keyword/reranking implementation supersedes the
earlier statement that these components had not yet been added; memory,
workflow logic, answer generation, and formal evaluation remain unimplemented.

## Phase 6 investigation engine

A compiled LangGraph StateGraph now wraps the existing Phase 5 retriever. Typed
per-run state flows through analysis, retrieval, evidence checking, generation
or insufficient-evidence fallback, and citation validation. The local generation
provider is qwen3.5:4b with an 8192-token context; embeddinggemma remains unchanged.
Ollama's installed MLX backend does not support native structured-output format,
so prompt-generated JSON is parsed with strict Pydantic schemas and rejected on
errors. Native mode remains configurable for future compatible backends; no
model/backend switch happens automatically.

Historical findings contain exact retrieved quotations with authoritative source
mapping attached by the application. Current hypotheses remain unconfirmed.
Synthetic resolution fields may be recovered verbatim from cited passages.
Unknown evidence or failed validation returns a general-guidance-only fallback.
Citation checks prove provenance and quotation membership, not full semantic
entailment. Sufficiency uses a conservative topic heuristic plus model judgment,
not calibrated similarity probabilities. No persistent checkpointing or Mem0 is
enabled; state lives for one graph invocation. No formal evaluation is implemented.

## Phase 7 archived — optional hosted investigation context (disabled)

The current optional scoped LangGraph path loads Mem0 before historical retrieval
and saves explicit user-reported troubleshooting facts after report validation.
The original unscoped Phase 6 path remains memory-free.

Mem0 Platform stores user context under a composite user/investigation identity;
session IDs record provenance without preventing cross-session recall. Returned
metadata is validated against both isolation keys. Pinecone remains the sole
historical-document citation source. Local Ollama and MiniLM still perform
generation/embedding and reranking; neither embeddings nor index schema changed.

Only user statements are written with `infer=False`. Generated hypotheses are
not memory facts. Append-only corrections replace active logical facts without
deleting old remote records. Explicit operation caps and no-retry transport
limit this approved run; usage and uncertain-write hashes are persisted locally.
Queued writes require later scoped reads. Memory outages warn and fall back to
existing historical retrieval. Scoped CLI commands are available; Streamlit is
unchanged. See the Phase 7 README section for actual verification and limitations.

## Phase 8 archived — original Streamlit presentation before memory removal

`app.py` → `home.render_home()` → `ui.render_app()`.

The UI's forms invoke existing `investigate(description, scope, memory)` only on
explicit submission. Explicit resume invokes the existing scoped Mem0 adapter.
All graph reasoning, hybrid retrieval, MiniLM reranking, and citation validation
remain in their existing modules. The UI creates no separate retrieval pipeline.

The shared local demo user is constant. The active investigation is stored in
URL query parameters and browser session state; a new browser session receives
a distinct session ID. Workspaces and form keys are partitioned by investigation.
Generated reports and conversational turns are temporary session state, while
user facts persist remotely through Mem0. Opening the app does not query services.
Resuming retrieves facts rather than a durable generated chat transcript.

A per-session in-flight flag and last-request fingerprint prevent immediate
accidental repeats. Results survive ordinary rerenders. No mutable scoped client
or LLM instance is globally cached; the preexisting local reranker cache remains.
Plain-text rendering, vetted public links, input screening, and generic error
messages protect the presentation boundary. This is a localhost demo, without
secure authentication, durable submission deduplication, or production access.

## Phase 9 — extractive source catalog

After retrieval, `evidence_catalog.py` builds bounded source excerpts with fact
IDs, real chunk IDs, offsets, titles, incident IDs, source types, and provenance.
The evidence gate and report-selection schemas enumerate allowed fact IDs.
The model selects facts; Python assembles source-anchored findings. Typed
synthetic fields supply causes/resolutions. Untyped public prose supplies neutral
observations, without heuristic causal-role promotion. Public excerpts can still
contain verbatim statements of documented causes or fixes.

Selected synthetic cause/resolution pairs are restored before validation.
Current hypotheses are optional and use a fixed unconfirmed template quoting a
selected validated mechanism verbatim. Local span/role/identity/rendering checks
augment existing quotation/citation checks. Unknown IDs and malformed structures
are rejected; nothing is fuzzily matched or silently discarded. Missing evidence
still follows the original insufficient-evidence path. The current source cannot
establish the current incident's cause merely because history is similar.

The original evaluation artifacts are unchanged. Phase 9 reports preserve both
the failed first experiment and the separately approved safer-revision run.
This is development-set re-evaluation, not independent held-out validation or
proof of general semantic entailment. Public fact-role extraction remains an
explicit limitation; free-form custom diagnostic reasoning is deliberately reduced.
