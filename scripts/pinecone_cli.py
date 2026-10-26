"""Read-only review by default; creation/upload require approval switches."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator import pinecone_store as store
from src.incident_investigator.providers import ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["review", "local", "create", "upload", "verify", "search", "keyword"])
    parser.add_argument("--approve-create", action="store_true")
    parser.add_argument("--approve-upload", action="store_true")
    parser.add_argument("--query", default="")
    args = parser.parse_args()
    if args.command == "review": result = store.review()
    elif args.command == "local": result = store.local_records()[2]
    elif args.command == "create": result = store.create_index(approved=args.approve_create)
    elif args.command == "upload": result = store.upload(approved=args.approve_upload)
    elif args.command == "verify": result = store.verify_remote()
    elif args.command == "keyword": result = store.keyword_search(args.query)
    else: result = store.semantic_search(args.query)
    print(json.dumps(result, indent=2))
    return 1 if result.get("error") or result.get("passed") is False else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc) if isinstance(exc, ProviderError) else "Pinecone operation failed. Check credentials, permissions, schema, and connectivity; raw server details suppressed.", file=sys.stderr)
        sys.exit(1)
