"""Run the two Phase 6 smoke examples, preserving retrieved evidence for audit."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.investigation import investigate
from src.incident_investigator.providers import ROOT, llm_provider
from check_local_llm import measure
from verify_phase6 import audit


if __name__ == "__main__":
    output = ROOT / "data/processed/phase6_verification"
    output.mkdir(exist_ok=True)
    summary = {}
    for name, query, expected in [
        ("sufficient", "Investigate HTTP 503 errors after deployment with unusually high database connections.", "investigation"),
        ("insufficient", "Investigate quantum processor decoherence after a cryogenic helium purge.", "insufficient_evidence"),
    ]:
        result, performance = measure(lambda: investigate(query))
        performance["api_ps_after_run"] = llm_provider().transport.request("/api/ps")
        result["performance"] = performance
        result["verification"] = audit(result)
        (output / (name + ".json")).write_text(json.dumps(result, indent=2))
        summary[name] = {"status": result["report"]["status"], "expected_status": expected,
                         "elapsed_seconds": result["elapsed_seconds"], "timings": result["timings"],
                         "retrieval_timings": result["retrieval_timings"], "verification": result["verification"]}
        print(json.dumps({name: summary[name]}, indent=2), flush=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    raise SystemExit(0 if all(s["status"] == s["expected_status"] and s["verification"]["passed"] for s in summary.values()) else 1)
