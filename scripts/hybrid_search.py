"""Demonstrate read-only hybrid search; optional local reranking."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.retrieval import hybrid_search

DEMO_QUERIES = ["HTTP 503 errors after deployment and exhausted database connections",
                "Database connection exhaustion causing checkout timeouts",
                "Deployment failures after missing production configuration"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()
    if not args.demo and not args.query:
        parser.error("Specify --query or --demo")
    queries = DEMO_QUERIES if args.demo else [args.query]
    results = [hybrid_search(q, False if args.no_rerank else None) for q in queries]
    print(json.dumps(results if args.demo else results[0], indent=2))
    sys.exit(1 if any(r.get("error") for r in results) else 0)
