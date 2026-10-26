"""Check source preservation, combined chunk coverage, and local vector links."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.ingestion import ROOT, validate
from src.incident_investigator.embedding_store import fingerprint, FORMAT
from src.incident_investigator.providers import settings, validate_vectors


def check():
    errors = []
    chunk_check = validate()
    errors.extend(chunk_check["errors"])
    synthetic = sorted((ROOT / "data/incidents/synthetic").glob("*.json"))
    public = sorted((ROOT / "data/incidents/public").glob("*.json"))
    baseline = json.loads((ROOT / "data/collection/synthetic_baseline.json").read_text())
    if len(synthetic) != 20 or any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h for p, h in baseline.items()):
        errors.append("Synthetic reports changed or missing")
    urls, titles, incident_ids = set(), set(), set()
    for path in synthetic + public:
        report = json.loads(path.read_text())
        incident_ids.add(report["incident_id"])
        if report["source_type"] == "public":
            url = urlsplit(report["source_url"])
            key = (url.hostname, url.path.rstrip("/"))
            if url.scheme not in {"http", "https"} or not url.hostname or not report.get("publisher") or not report.get("retrieved_at"):
                errors.append(f"Untraceable public report: {path.name}")
            if key in urls or report["title"].casefold() in titles:
                errors.append(f"Duplicate public report: {path.name}")
            urls.add(key); titles.add(report["title"].casefold())
    chunks = [json.loads(line) for line in (ROOT / "data/processed/chunks.jsonl").read_text().splitlines()]
    vectors = [json.loads(line) for line in (ROOT / "data/local_embeddings/embeddings.jsonl").read_text().splitlines()]
    manifest = json.loads((ROOT / "data/local_embeddings/verification.json").read_text())
    config = settings()
    if manifest.get("model") != config["embedding_model"] or manifest.get("provider") != config["embedding_provider"] or manifest.get("configuration") != FORMAT:
        errors.append("Embedding configuration mismatch")
    if manifest.get("source_sha256") != hashlib.sha256((ROOT / "data/processed/chunks.jsonl").read_bytes()).hexdigest():
        errors.append("Embedding snapshot is stale")
    by_id = {row["id"]: row for row in vectors}
    if len(by_id) != len(vectors) or set(by_id) != {c["id"] for c in chunks}:
        errors.append("Chunk/vector IDs differ or duplicate vectors")
    if {c["metadata"]["incident_id"] for c in chunks} != incident_ids:
        errors.append("Not every incident is represented")
    for chunk in chunks:
        row = by_id.get(chunk["id"], {})
        if row.get("page_content") != chunk["page_content"] or row.get("metadata") != chunk["metadata"]:
            errors.append(f"Vector content or metadata mismatch: {chunk['id']}")
        if row.get("embedding_fingerprint") != fingerprint(chunk["page_content"], manifest):
            errors.append(f"Fingerprint mismatch: {chunk['id']}")
    if validate_vectors([r["values"] for r in vectors], len(chunks)) != 768:
        errors.append("Expected 768 dimensions")
    usage = json.loads((ROOT / "data/collection/usage.json").read_text())
    if usage["reserved_credits"] > 13 or usage["reported_credits"] > 13 or usage["search_calls"] > 7 or usage["extract_calls"] > 6:
        errors.append("Tavily approved limits exceeded")
    summary = json.loads((ROOT / "data/processed/ingestion_summary.json").read_text())
    return {"passed": not errors, "synthetic_incidents": len(synthetic), "public_incidents": len(public),
            "total_incidents": len(incident_ids), "total_processed_chunks": len(chunks),
            "newly_generated_embeddings": manifest["newly_generated_embeddings"], "reused_embeddings": manifest["reused_embeddings"],
            "failed_documents": len(summary["invalid_documents"]), "embedding_dimensions": 768,
            "tavily_reported_credits": usage["reported_credits"], "tavily_search_calls": usage["search_calls"],
            "tavily_extract_calls": usage["extract_calls"], "validation_errors": errors}


if __name__ == "__main__":
    try:
        result = check()
        (ROOT / "data/processed/knowledge_base_summary.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["passed"] else 1)
    except Exception:
        print("Knowledge-base validation failed: missing or malformed local artifacts.", file=sys.stderr)
        sys.exit(1)
