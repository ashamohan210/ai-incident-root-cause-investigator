"""Run from any working directory with the project virtual environment."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.ingestion import ingest

if __name__ == "__main__":
    summary = ingest()
    print(json.dumps(summary, indent=2))
    sys.exit(1 if summary["invalid_documents"] or summary["missing_incident_ids"] else 0)
