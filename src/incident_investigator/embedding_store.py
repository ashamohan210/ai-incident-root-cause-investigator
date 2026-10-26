"""Repeatable local vector snapshots with content/model/configuration reuse."""
import hashlib
import json

from .providers import ROOT, ProviderError, embedding_provider, validate_vectors

OUT = ROOT / "data/local_embeddings"
FORMAT = "embeddinggemma-retrieval-prefixes-v1:truncate=false:dimensions=native"


def fingerprint(text, info):
    return hashlib.sha256(json.dumps([text, "ollama", info["model"], info["model_digest"], FORMAT], ensure_ascii=False).encode()).hexdigest()


def refresh():
    provider = embedding_provider()
    info = provider.availability()
    if not info.get("model_digest"):
        raise ProviderError("Cannot validate model identity without an Ollama digest.")
    source = ROOT / "data/processed/chunks.jsonl"
    raw = source.read_bytes()
    chunks = [json.loads(line) for line in raw.decode().splitlines()]
    if not chunks or len({r["id"] for r in chunks}) != len(chunks):
        raise ProviderError("Empty or duplicate processed chunks")
    old = []
    manifest = {}
    if (OUT / "embeddings.jsonl").exists():
        old = [json.loads(line) for line in (OUT / "embeddings.jsonl").read_text().splitlines()]
        manifest = json.loads((OUT / "verification.json").read_text())
    snapshot = ROOT / "data/processed/phase3_chunks.jsonl"
    # Legacy migration requires the known Phase 3 source fingerprint and the
    # same provider, model digest, native dimensions, and documented task format.
    legacy_valid = (
        snapshot.exists() and manifest.get("source_sha256") == hashlib.sha256(snapshot.read_bytes()).hexdigest()
        and manifest.get("provider") == "ollama" and manifest.get("model") == info["model"]
        and manifest.get("model_digest") == info["model_digest"] and manifest.get("dimensions") == 768
    )
    cache = {}
    for row in old:
        try:
            if validate_vectors([row["values"]], 1) != 768:
                continue
            key = row.get("embedding_fingerprint")
            if key and key != fingerprint(row["page_content"], info):
                continue
            if not key and legacy_valid:
                key = fingerprint(row["page_content"], info)
            if key:
                cache[key] = row["values"]
        except (ProviderError, KeyError, TypeError):
            continue
    rows, pending = [], []
    reused = 0
    for chunk in chunks:
        if not chunk.get("page_content", "").strip() or not chunk.get("metadata", {}).get("incident_id"):
            raise ProviderError("Invalid chunk content or incident metadata")
        key = fingerprint(chunk["page_content"], info)
        row = {**chunk, "embedding_fingerprint": key, "values": cache.get(key)}
        rows.append(row)
        if row["values"] is None:
            pending.append(row)
        else:
            reused += 1
    for start in range(0, len(pending), 4):
        batch = pending[start:start + 4]
        vectors = provider.embed_documents([r["page_content"] for r in batch])
        if validate_vectors(vectors, len(batch)) != 768:
            raise ProviderError("Expected 768 embedding dimensions; refusing to save incompatible vectors")
        for row, vector in zip(batch, vectors):
            row["values"] = vector
    validate_vectors([row["values"] for row in rows], len(rows))
    report = {**info, "provider": "ollama", "configuration": FORMAT, "dimensions": 768,
              "chunks_embedded": len(rows), "newly_generated_embeddings": len(pending),
              "reused_embeddings": reused, "source_sha256": hashlib.sha256(raw).hexdigest(),
              "pinecone_created": False}
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in {"embeddings.jsonl": "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                       "verification.json": json.dumps(report, indent=2) + "\n"}.items():
        temporary = OUT / (name + ".tmp")
        temporary.write_text(text)
        temporary.replace(OUT / name)
    return report
