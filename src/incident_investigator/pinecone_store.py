"""Pinecone SDK 10 document interface; writes require explicit approval flags."""
import hashlib
import json
import os
import tomllib

from dotenv import load_dotenv
from pinecone import DenseVectorQuery, Pinecone, TextQuery

from .embedding_store import FORMAT, fingerprint
from .providers import ROOT, ProviderError, embedding_provider, validate_vectors

METADATA_FIELDS = ("incident_id", "title", "category", "affected_service", "source_type",
                   "source_url", "source", "chunk_number")


def config():
    return tomllib.loads((ROOT / "config/pinecone.toml").read_text())


def proposed_schema():
    """Declare searchable fields only; metadata accompanies each document."""
    from pinecone import SchemaBuilder
    cfg = config()
    return (SchemaBuilder()
            .add_dense_vector_field(cfg["vector_field"], dimension=cfg["dimension"], metric=cfg["metric"])
            .add_string_field("chunk_text", full_text_search={"language": "en", "stemming": False, "stop_words": False})
            .build())


def client():
    load_dotenv(ROOT / ".env", override=False)
    key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not key:
        raise ProviderError("PINECONE_API_KEY is missing from local .env/environment.")
    return Pinecone(api_key=key, timeout=30)


def local_records():
    cfg = config()
    raw = (ROOT / "data/processed/chunks.jsonl").read_bytes()
    chunks = [json.loads(line) for line in raw.decode().splitlines()]
    vectors = [json.loads(line) for line in (ROOT / "data/local_embeddings/embeddings.jsonl").read_text().splitlines()]
    manifest = json.loads((ROOT / "data/local_embeddings/verification.json").read_text())
    if manifest.get("source_sha256") != hashlib.sha256(raw).hexdigest() or manifest.get("configuration") != FORMAT:
        raise ProviderError("Embedding snapshot is stale or has an unsupported task configuration.")
    if manifest.get("provider") != "ollama" or manifest.get("model") != "embeddinggemma:300m" or not manifest.get("model_digest"):
        raise ProviderError("Unexpected embedding provider/model identity.")
    if validate_vectors([r["values"] for r in vectors], len(chunks)) != cfg["dimension"]:
        raise ProviderError("Vector dimension differs from proposed Pinecone dimension.")
    indexed = {r["id"]: r for r in vectors}
    if len(indexed) != len(vectors) or set(indexed) != {r["id"] for r in chunks} or len({r["id"] for r in chunks}) != len(chunks):
        raise ProviderError("Duplicate IDs or unmatched chunks/vectors.")
    records, sizes = [], []
    for chunk in chunks:
        row = indexed[chunk["id"]]
        if row["page_content"] != chunk["page_content"] or row["metadata"] != chunk["metadata"] or row.get("embedding_fingerprint") != fingerprint(chunk["page_content"], manifest):
            raise ProviderError("Embedding content, metadata, or fingerprint mismatch.")
        if not chunk["page_content"].strip():
            raise ProviderError("Empty chunk")
        metadata = {key: chunk["metadata"].get(key) for key in METADATA_FIELDS}
        for key in ("incident_id", "title", "category", "source_type", "source", "chunk_number"):
            if not metadata.get(key):
                raise ProviderError(f"Missing required metadata: {key}")
        # Pinecone metadata omits unknown values; search restores them as None.
        metadata = {key: value for key, value in metadata.items() if value is not None}
        metadata.update(chunk_text=chunk["page_content"], embedding_model=manifest["model"],
                        embedding_digest=manifest["model_digest"], embedding_fingerprint=row["embedding_fingerprint"])
        size = len(json.dumps(metadata, ensure_ascii=False).encode())
        if size >= 40_000 or len(row["id"]) > 512:
            raise ProviderError("Metadata or ID exceeds conservative Pinecone limits.")
        sizes.append(size)
        records.append({"_id": row["id"], cfg["vector_field"]: row["values"], **metadata})
    return records, manifest, {"vector_count": len(records), "dimension": cfg["dimension"],
                               "maximum_metadata_bytes": max(sizes), "total_metadata_bytes": sum(sizes),
                               "raw_float32_vector_bytes": len(records) * cfg["dimension"] * 4}


def expected_tags(manifest):
    return {"embedding_model": manifest["model"], "embedding_digest": manifest["model_digest"],
            "embedding_config": hashlib.sha256(FORMAT.encode()).hexdigest()}


def compatible(description, manifest, require_identity=True):
    cfg = config()
    data = description.to_dict()
    fields = data.get("schema", {}).get("fields", {})
    field = fields.get(cfg["vector_field"], {})
    if field.get("type") != "dense_vector" or field.get("dimension") != cfg["dimension"] or field.get("metric") != cfg["metric"] or any(name.startswith("_") for name in fields):
        raise ProviderError("Incompatible index schema/interface. Expected Documents API with embedding: dense 768/cosine. No changes made.")
    text_field = fields.get("chunk_text", {})
    if text_field.get("type") != "string" or not isinstance(text_field.get("full_text_search"), dict) or text_field.get("filterable") is True:
        raise ProviderError("Index lacks full-text searchable chunk_text. No changes made.")
    if require_identity and any((data.get("tags") or {}).get(k) != v for k, v in expected_tags(manifest).items()):
        raise ProviderError("Index embedding identity is unverified or different. Refusing to mix model spaces.")
    if not data.get("status", {}).get("ready"):
        raise ProviderError("Index is not ready yet; retry later.")
    return data


def review():
    records, manifest, metrics = local_records()
    pc = client()
    cfg = config()
    exists = any(index.name == cfg["index_name"] for index in pc.indexes.list())
    result = {"proposal": cfg, "schema": proposed_schema(), "local_verification": metrics, "key_connectivity": "ok", "index_exists": exists,
              "sdk_interface": "documents", "billing_plan_and_credits": "not exposed by project index API; check Pinecone console",
              "account_region_entitlements": "not exposed by project index API; aws/us-east-1 proposed for Starter compatibility"}
    if exists:
        desc = pc.indexes.describe(cfg["index_name"])
        try:
            compatible(desc, manifest)
            result["existing_index_compatible"] = True
        except ProviderError as exc:
            result["existing_index_compatible"] = False
            result["compatibility_issue"] = str(exc)
    return result


def create_index(*, approved=False):
    if not approved:
        raise ProviderError("Creation requires explicit approval; no external write made.")
    _, manifest, _ = local_records()
    cfg = config()
    pc = client()
    if any(index.name == cfg["index_name"] for index in pc.indexes.list()):
        compatible(pc.indexes.describe(cfg["index_name"]), manifest)
        return {"created": False, "reused": True}
    pc.indexes.create(name=cfg["index_name"], schema=proposed_schema(),
        deployment={"deployment_type": "managed", "cloud": cfg["cloud"], "region": cfg["region"]},
        deletion_protection=cfg["deletion_protection"], tags=expected_tags(manifest), timeout=60)
    return {"created": True, "index": cfg["index_name"]}


def open_index(manifest):
    pc = client()
    desc = pc.indexes.describe(config()["index_name"])
    data = compatible(desc, manifest)
    return pc.index(host=data["host"])


def upload(*, approved=False):
    if not approved:
        raise ProviderError("Upload requires explicit approval; no external write made.")
    records, manifest, _ = local_records()
    cfg = config()
    index = open_index(manifest)
    for start in range(0, len(records), cfg["batch_size"]):
        batch = records[start:start + cfg["batch_size"]]
        if len(json.dumps({"namespace": cfg["namespace"], "documents": batch}).encode()) >= 1_900_000:
            raise ProviderError("Batch exceeds safe request size.")
        index.documents.upsert(namespace=cfg["namespace"], documents=batch)
    return {"submitted": len(records), "namespace": cfg["namespace"], "note": "Run verify after eventual consistency settles."}


def verify_remote():
    records, manifest, _ = local_records()
    cfg = config()
    index = open_index(manifest)
    stats = index.describe_index_stats().to_dict()
    count = stats.get("namespaces", {}).get(cfg["namespace"], {}).get("vector_count", 0)
    found, errors = set(), []
    for start in range(0, len(records), cfg["batch_size"]):
        batch = records[start:start + cfg["batch_size"]]
        response = index.documents.fetch(namespace=cfg["namespace"], ids=[r["_id"] for r in batch],
                                         include_fields=list(METADATA_FIELDS) + ["chunk_text", "embedding_fingerprint"])
        for document in response.documents.values():
            found.add(document.id)
            expected = next(r for r in batch if r["_id"] == document.id)
            if any(document.get(key) != expected.get(key) for key in (*METADATA_FIELDS, "chunk_text", "embedding_fingerprint")):
                errors.append(document.id)
    return {"expected_count": len(records), "namespace_count": count, "expected_ids_found": len(found),
            "metadata_mismatches": errors, "passed": count == len(records) and len(found) == len(records) and not errors}


def semantic_search(description: str, top_k: int = 5):
    try:
        if not isinstance(description, str) or not description.strip():
            raise ProviderError("Enter a non-empty incident description.")
        _, manifest, _ = local_records()
        provider = embedding_provider()
        info = provider.availability()
        if info["model"] != manifest["model"] or info["model_digest"] != manifest["model_digest"]:
            raise ProviderError("Local query model differs from the stored document model.")
        vector = provider.embed_query(description)
        if validate_vectors([vector], 1) != 768:
            raise ProviderError("Query embedding must have 768 dimensions.")
        cfg = config()
        response = open_index(manifest).documents.search(namespace=cfg["namespace"], top_k=top_k,
            score_by=[DenseVectorQuery(field=cfg["vector_field"], values=vector)],
            include_fields=list(METADATA_FIELDS) + ["chunk_text"])
        results = [{"id": hit.id, "score": hit.score, **{key: hit.get(key) for key in METADATA_FIELDS},
                    "chunk_text": hit.get("chunk_text")} for hit in response.matches]
        if any(not row["incident_id"] or not row["source"] or not row["chunk_text"] for row in results):
            raise ProviderError("Search returned records without required source evidence.")
        return {"results": results, "error": None}
    except Exception as exc:
        return {"results": [], "error": str(exc) if isinstance(exc, ProviderError) else "Pinecone/Ollama request failed. Check credentials, index readiness, and service availability."}


def keyword_search(description: str, top_k: int = 10):
    """BM25 over the existing chunk_text field; no embedding or index writes."""
    try:
        if not isinstance(description, str) or not description.strip():
            raise ProviderError("Enter a non-empty incident description.")
        _, manifest, _ = local_records()
        response = open_index(manifest).documents.search(
            namespace=config()["namespace"], top_k=top_k,
            score_by=[TextQuery(query=description, fields=["chunk_text"])],
            include_fields=list(METADATA_FIELDS) + ["chunk_text"])
        results = [{"id": hit.id, "score": hit.score, **{key: hit.get(key) for key in METADATA_FIELDS},
                    "chunk_text": hit.get("chunk_text")} for hit in response.matches]
        if any(not r["incident_id"] or not r["source"] or not r["chunk_text"] for r in results):
            raise ProviderError("Keyword search returned incomplete source metadata.")
        return {"results": results, "error": None}
    except Exception as exc:
        return {"results": [], "error": str(exc) if isinstance(exc, ProviderError) else "Pinecone keyword search failed; check service availability and chunk_text search support."}
