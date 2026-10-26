"""Local regression checks; fixtures reuse existing incident content."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from langchain_core.documents import Document
from src.incident_investigator.ingestion import (
    INPUT, OUTPUT, ROOT, IncidentJSONLoader, chunk_document, encoding, ingest,
    prepare, validate,
)


class IngestionTests(unittest.TestCase):
    def test_repeatable_and_sources_unchanged(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in INPUT.glob("*.json")}
        ingest()
        snapshot = (OUTPUT / "chunks.jsonl").read_bytes()
        ingest()
        self.assertEqual(snapshot, (OUTPUT / "chunks.jsonl").read_bytes())
        self.assertTrue(validate()["passed"])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_long_document_overlap_and_size(self):
        original = IncidentJSONLoader(INPUT / "SYN-001.json").load()[0]
        document = Document(page_content=(original.page_content + "\n\n") * 5,
                            metadata=original.metadata)
        chunks = chunk_document(document)
        self.assertGreater(len(chunks), 1)
        enc = encoding()
        for previous, current in zip(chunks, chunks[1:]):
            self.assertTrue(current["page_content"].startswith(
                enc.decode(enc.encode(previous["page_content"])[-75:])))
            self.assertEqual(current["metadata"]["overlap_tokens"], 75)
        self.assertTrue(all(0 < c["metadata"]["token_count"] <= 600 for c in chunks))

    def test_bad_sources_are_reported(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data") as directory:
            folder = Path(directory)
            (folder / "broken.json").write_text("{")
            (folder / "missing.json").write_text(json.dumps({"incident_id": "SYN-001"}))
            chunks, summary = prepare(folder)
            self.assertEqual(chunks, [])
            self.assertEqual(len(summary["invalid_documents"]), 2)
            self.assertEqual(len(summary["missing_incident_ids"]), 20)

    def test_validator_rejects_empty_content(self):
        path = OUTPUT / "chunks.jsonl"
        original = path.read_bytes()
        try:
            rows = [json.loads(line) for line in original.decode().splitlines()]
            rows[0]["page_content"] = ""
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.assertFalse(validate()["passed"])
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
