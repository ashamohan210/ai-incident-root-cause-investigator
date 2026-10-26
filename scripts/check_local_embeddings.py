"""Refresh local embeddings, reusing compatible content/model fingerprints."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.embedding_store import refresh
from src.incident_investigator.providers import ProviderError

if __name__ == "__main__":
    try:
        print(json.dumps(refresh(), indent=2))
    except Exception as exc:
        print(str(exc) if isinstance(exc, ProviderError) else "Embedding refresh failed; check local Ollama and processed files.", file=sys.stderr)
        sys.exit(1)
