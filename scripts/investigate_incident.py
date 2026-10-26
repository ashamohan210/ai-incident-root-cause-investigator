"""Run the local LangGraph investigation using existing read-only retrieval."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.investigation import investigate
from src.incident_investigator.providers import llm_provider
from check_local_llm import measure

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    try:
        result, performance = measure(lambda: investigate(args.query))
        performance["api_ps_after_run"] = llm_provider().transport.request("/api/ps")
        result["performance"] = performance
        print(json.dumps(result, indent=2))
    except Exception:
        print("Investigation could not complete. Check local model readiness and configuration; no conclusion generated.", file=sys.stderr)
        sys.exit(1)
