"""Local, deterministic incident document preparation. No model calls."""

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/incidents/synthetic"
OUTPUT = ROOT / "data/processed"
FIELDS = (
    "incident_id", "title", "category", "affected_service", "severity",
    "symptoms", "error_codes", "root_cause", "resolution", "source_type",
)


def clean(text: str) -> str:
    """Normalize layout, preserving punctuation, case, and technical codes."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in text.splitlines())).strip()


class IncidentJSONLoader(BaseLoader):
    """One JSON file becomes one LangChain Document.

    Future PDF loaders (including LlamaParse) can implement the same BaseLoader
    interface and return Documents to chunk_document. No PDF parsing runs here.
    """

    def __init__(self, path: Path):
        self.path = path

    def lazy_load(self) -> Iterator[Document]:
        item = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(item, dict):
            raise ValueError("Expected a JSON object")
        if item.get("source_type") == "public":
            for field in ("incident_id", "title", "publisher", "source_url", "retrieved_at", "full_report"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError(f"Missing public field: {field}")
            if not re.fullmatch(r"PUB-[0-9a-f]{12}", item["incident_id"]):
                raise ValueError("Invalid public ID")
            if urlsplit(item["source_url"]).scheme not in {"http", "https"} or not urlsplit(item["source_url"]).hostname:
                raise ValueError("Invalid public source URL")
            if len(item["full_report"]) < 800:
                raise ValueError("Insufficient public incident evidence")
            metadata = {key: item.get(key) for key in (*FIELDS, "source_url", "publisher", "incident_date", "retrieved_at")}
            metadata["source"] = self.path.resolve().relative_to(ROOT).as_posix()
            metadata["source_sha256"] = hashlib.sha256(self.path.read_bytes()).hexdigest()
            # Keep the technical narrative in source order; do not duplicate long
            # evidence sections in a header or synthesize missing facts.
            yield Document(page_content=clean(item["full_report"]), metadata=metadata)
            return
        for field in (*FIELDS, "full_report"):
            value = item.get(field)
            if field == "error_codes":
                valid = isinstance(value, list) and bool(value) and all(
                    isinstance(code, str) and code.strip() for code in value
                )
            else:
                valid = isinstance(value, str) and bool(value.strip())
            if not valid:
                raise ValueError(f"Missing or invalid field: {field}")
        if not re.fullmatch(r"SYN-\d{3}", item["incident_id"]):
            raise ValueError("Invalid synthetic incident ID")
        if item["source_type"] != "synthetic":
            raise ValueError("Expected source_type=synthetic")
        metadata = {field: item[field] for field in FIELDS}
        metadata["source_url"] = item.get("source_url")
        metadata["source"] = self.path.resolve().relative_to(ROOT).as_posix()
        metadata["source_sha256"] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        # Some Phase 2 files contain literal backslash-n sequences in full_report.
        report = item["full_report"].replace("\\n", "\n")
        header = "\n".join(
            f"{field}: {', '.join(item[field]) if isinstance(item[field], list) else item[field]}"
            for field in FIELDS
        )
        yield Document(page_content=clean(header + "\n\n" + report), metadata=metadata)


def encoding():
    # The first run downloads tokenizer vocabulary, not a model or paid service.
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / ".tokenizer-cache"))
    return tiktoken.get_encoding("cl100k_base")


def chunk_document(document: Document) -> list[dict]:
    enc = encoding()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=520 if document.metadata.get("source_type") == "public" else 525, chunk_overlap=0,
        length_function=lambda text: len(enc.encode(text, disallowed_special=())),
        separators=(["\n\n", "\n", ". ", " ", ""] if document.metadata.get("source_type") == "public"
                    else ["\n\n## ", "\n\n", "\n", ". ", " ", ""]),
        keep_separator=True, strip_whitespace=False,
    )
    # Preserve whole headings/paragraphs/fields whenever they fit. Repeat exactly
    # 75 tokens from the previous chunk as context; do not split incident boundaries.
    pieces = splitter.split_documents([document])
    chunks = []
    for number, piece in enumerate(pieces, 1):
        overlap = enc.encode(chunks[-1]["page_content"], disallowed_special=())[-75:] if chunks else []
        prefix = enc.decode(overlap) if overlap else ""
        content = prefix + piece.page_content
        metadata = dict(piece.metadata, chunk_number=number, total_chunks=len(pieces),
                        token_count=len(enc.encode(content, disallowed_special=())),
                        overlap_tokens=len(overlap), tokenizer="cl100k_base")
        chunks.append({"id": f"{metadata['incident_id']}:chunk:{number:03d}",
                       "page_content": content, "metadata": metadata})
    return chunks


def prepare(input_dir: Path | None = None) -> tuple[list[dict], dict]:
    paths = sorted(input_dir.glob("*.json")) if input_dir is not None else (
        sorted(INPUT.glob("*.json")) + sorted((INPUT.parent / "public").glob("*.json")))
    chunks, invalid, seen = [], [], set()
    sources, titles, reports = set(), set(), set()
    counts = {"synthetic": 0, "public": 0}
    for path in paths:
        try:
            document = IncidentJSONLoader(path).load()[0]
            incident_id = document.metadata["incident_id"]
            if incident_id in seen:
                raise ValueError(f"Duplicate incident ID: {incident_id}")
            if document.metadata["source_type"] == "public":
                url = urlsplit(document.metadata["source_url"])
                key = (url.hostname, url.path.rstrip("/"))
                title = document.metadata["title"].casefold()
                digest = hashlib.sha256(document.page_content.encode()).hexdigest()
                if key in sources or title in titles or digest in reports:
                    raise ValueError("Duplicate public report URL, title, or content")
                sources.add(key); titles.add(title); reports.add(digest)
            incident_chunks = chunk_document(document)
            seen.add(incident_id)
            counts[document.metadata["source_type"]] += 1
            chunks.extend(incident_chunks)
        except (ValueError, OSError, UnicodeError) as exc:
            invalid.append({"source": str(path), "error": str(exc)})
    missing = sorted({f"SYN-{i:03d}" for i in range(1, 21)} - seen)
    summary = {
        "total_incident_files_read": len(paths), "valid_incidents": len(seen),
        "synthetic_incidents": counts["synthetic"], "public_incidents": counts["public"],
        "total_chunks_generated": len(chunks),
        "average_chunks_per_incident": round(len(chunks) / len(seen), 2) if seen else 0,
        "missing_incident_ids": missing, "invalid_documents": invalid,
        "tokenizer": "cl100k_base", "max_tokens": 600, "overlap_tokens": 75,
        "chunk_token_counts": [chunk["metadata"]["token_count"] for chunk in chunks],
    }
    return chunks, summary


def ingest() -> dict:
    chunks, summary = prepare()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Replace the snapshot rather than appending, so reruns never add duplicates.
    for name, text in {
        "chunks.jsonl": "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        "ingestion_summary.json": json.dumps(summary, indent=2) + "\n",
    }.items():
        temporary = OUTPUT / (name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(OUTPUT / name)
    return summary


def validate() -> dict:
    """Compare stored chunks with current sources, including provenance/content."""
    expected, summary = prepare()
    errors = []
    try:
        actual = [json.loads(line) for line in (OUTPUT / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        if not actual:
            errors.append("No stored chunks")
        if actual != expected:
            errors.append("Stored chunks differ from current sources/processing; rerun ingestion")
        ids = set()
        for row in actual:
            if not isinstance(row, dict):
                errors.append("Invalid chunk object")
                continue
            metadata = row.get("metadata", {})
            if not isinstance(row.get("page_content"), str) or not row["page_content"].strip():
                errors.append("Empty chunk content")
            if not isinstance(metadata, dict) or not metadata.get("incident_id") or not metadata.get("source"):
                errors.append("Missing traceable incident ID/source")
            identifier = row.get("id")
            if not isinstance(identifier, str) or identifier in ids:
                errors.append("Invalid or duplicate chunk ID")
            else:
                ids.add(identifier)
    except (OSError, ValueError, UnicodeError) as exc:
        actual = []
        errors.append(str(exc))
    if summary["invalid_documents"] or summary["missing_incident_ids"]:
        errors.append("Missing or invalid source incidents; see ingestion summary")
    if any(row["metadata"]["token_count"] > 600 for row in expected):
        errors.append("Chunk exceeds 600 tokens")
    return {"passed": not errors, "chunks_checked": len(actual),
            "incidents_checked": summary["valid_incidents"], "errors": errors}
