"""Hosted investigation memory: scoped operations, no deletion command."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.memory import Scope, InvestigationMemory, MemoryUnavailable, UsageGuard, require_memory_enabled
from src.incident_investigator.investigation import investigate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "list", "add", "correct", "ask", "usage"])
    parser.add_argument("--user-id")
    parser.add_argument("--investigation-id")
    parser.add_argument("--session-id")
    parser.add_argument("--text", default="")
    parser.add_argument("--kind", default="user_fact")
    parser.add_argument("--memory-id")
    args = parser.parse_args()
    try:
        if args.command == "usage":
            result = UsageGuard().snapshot()
        else:
            require_memory_enabled()
            if not all((args.user_id, args.investigation_id, args.session_id)):
                parser.error("user-id, investigation-id, and session-id are all required")
            scope = Scope(args.user_id, args.investigation_id, args.session_id)
            if args.command == "ask":
                result = investigate(args.text, scope=scope)
            else:
                adapter = InvestigationMemory()
                if args.command == "create": result = adapter.create_investigation(scope, args.text)
                elif args.command == "list": result = adapter.retrieve(scope)
                elif args.command == "add": result = adapter.add_fact(scope, args.kind, args.text)
                else: result = adapter.supersede(scope, args.memory_id, args.text)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(str(exc) if isinstance(exc, (MemoryUnavailable, ValueError)) else "Memory operation failed; raw response and credentials suppressed.", file=sys.stderr)
        sys.exit(1)
