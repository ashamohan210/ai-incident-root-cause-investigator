"""Audit saved live-run evidence and report wording; makes no API calls."""
import argparse
import json
from pathlib import Path


def audit(result):
    report = result["report"]
    evidence = {row["id"]: row for row in result["retrieved_evidence"]}
    errors, checked = [], 0
    for section in ("historical_root_causes", "previous_resolutions", "historical_observations"):
        for claim in report[section]:
            checked += 1
            row = evidence.get(claim["chunk_id"])
            if row is None or claim["supporting_passage"].strip() not in row["chunk_text"]:
                errors.append("Unsupported historical quotation: " + claim["chunk_id"])
                continue
            if any(claim.get(key) != row.get(key) for key in ("incident_id", "title", "source_type", "source_url")) or claim["source_file"] != row["source"]:
                errors.append("Source metadata mismatch: " + claim["chunk_id"])
    if report["current_root_cause_confirmed"] is not False:
        errors.append("Current cause was presented as confirmed")
    for hypothesis in report["current_incident_hypotheses"]:
        if hypothesis["status"] != "unconfirmed hypothesis" or not hypothesis["hypothesis"].startswith("Possible explanation to investigate (not established): "):
            errors.append("Hypothesis lacks explicit uncertainty")
        if any(identifier not in evidence for identifier in hypothesis["supporting_chunk_ids"]):
            errors.append("Hypothesis cites a passage that was not retrieved")
    if report["citation_validation_issues"] and report["status"] == "investigation":
        errors.append("Accepted report contains citation validation issues")
    if report["status"] == "insufficient_evidence" and any(report[key] for key in ("historical_root_causes", "previous_resolutions", "current_incident_hypotheses")):
        errors.append("Insufficient-evidence response invented findings")
    return {"passed": not errors, "historical_claims_checked": checked, "errors": errors,
            "note": "Checks retrieved-source membership, exact quotations, source metadata, and uncertainty labels; does not prove semantic entailment."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text()))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
