#!/usr/bin/env python3
"""Phase 2: Create a synthetic IT incident dataset; validate synthetic + public JSON.

No external API, requests, or third-party libraries required.
Usage:
    python phase2_incident_dataset.py generate
    python phase2_incident_dataset.py validate
    python phase2_incident_dataset.py all

Run in the root of your AI Incident RCA project. Public reports must be sourced
and added separately; this script never fabricates real incidents.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "data" / "incidents"
SYNTHETIC = BASE / "synthetic"
PUBLIC = BASE / "public"
REPORT = BASE / "dataset_summary.json"

# Distinct, fictional scenarios; some have similar symptoms with different causes.
# (category, service, symptom, code, root cause, diagnostic signal, fix, prevention)
SCENARIOS = [
    ("database", "Payments API", "HTTP 503 responses and elevated DB connections", "HTTP 503", "A deployment increased connection-pool limits beyond the database server's capacity", "DB active-session count rose immediately after the deployment while connection timeout logs spiked", "Restore safe pool limits and restart affected workers in a controlled rollout", "Load-test connection settings against actual DB limits and alert on pool saturation"),
    ("database", "Orders Service", "Requests timing out during checkout", "SQLSTATE 55P03", "A long-running transaction held a lock needed by checkout writes", "Blocked-query metrics and lock wait events pointed to a single long-lived transaction", "Terminate the blocking transaction after review and shorten the transaction scope", "Add lock-wait alerting and enforce transaction duration limits"),
    ("database", "Inventory API", "Read latency jumped after a schema change", "SQLSTATE 57014", "A new query plan performed table scans because a critical index was absent", "EXPLAIN showed sequential scans and high rows-read counts", "Add the missing index using an online migration and recheck query plans", "Review query plans during migration testing"),
    ("database", "Analytics Warehouse", "Scheduled ETL job stopped updating dashboards", "ETL-204", "An expired warehouse service credential prevented the nightly load", "Job logs showed authentication errors for the warehouse service account", "Rotate the credential and replay missed ingestion batches", "Automate credential rotation with expiration alerts"),
    ("api", "Checkout Gateway", "HTTP 503 errors after rolling deployment", "HTTP 503", "Readiness probes pointed traffic at instances before they completed initialization", "Traffic logs showed 503s from freshly created instances with incomplete startup checks", "Correct readiness probe criteria and roll back the faulty release", "Add end-to-end readiness tests in deployment pipelines"),
    ("api", "User Profile API", "HTTP 503 errors during peak usage", "HTTP 503", "Thread-pool exhaustion caused request queues to overflow under load", "Application thread counts hit configured limits while database connections remained normal", "Increase capacity and optimize a blocking downstream client", "Introduce concurrency budgets and saturation alerting"),
    ("api", "Notifications Service", "Duplicate emails sent to customers", "MSG-DUP", "A retry handler was not idempotent after a broker redelivery", "Same message ID appeared in several successful send records", "Implement an idempotency key and stop duplicate-processing workers", "Test at-least-once delivery and duplicate-message handling"),
    ("api", "Search API", "Intermittent 504 gateway timeouts", "HTTP 504", "A downstream search shard became overloaded during an expensive aggregation", "Shard CPU and slow-query logs correlated with latency spikes", "Cancel the expensive query and tune aggregation limits", "Set query budgets and canary large aggregations"),
    ("cloud", "Image Processing Workers", "Processing jobs stayed in pending state", "K8S-PENDING", "Cluster node quotas prevented the autoscaler from provisioning capacity", "Scheduler events reported insufficient CPU and quota exceeded", "Increase approved node quota and reduce resource requests", "Alert on quota utilization and run capacity forecasts"),
    ("cloud", "Object Storage Uploads", "File uploads failed sporadically", "HTTP 403", "A storage bucket policy change removed the uploader role's write permission", "Cloud audit logs showed a permission policy edit preceding failures", "Restore the minimum required write permission", "Run policy change simulations and guardrails before rollout"),
    ("cloud", "Event Ingestion", "Queue backlog expanded rapidly", "QUEUE-LAG", "A consumer autoscaling policy was disabled during infrastructure migration", "Queue depth climbed while consumer replica count stayed fixed", "Restore autoscaling and drain the backlog gradually", "Continuously validate autoscaling policies after migration"),
    ("cloud", "Customer Portal", "Increased error rates across one availability zone", "AZ-UNHEALTHY", "Traffic balancing continued sending requests to an unhealthy zone", "Zone-specific health metrics diverged and the load balancer retained unhealthy targets", "Drain impacted targets and correct zone health-check routing", "Test zonal failover and improve health-check coverage"),
    ("deployment", "Billing Service", "HTTP 500 errors immediately after release", "HTTP 500", "An incompatible configuration key was missing from the production environment", "Startup logs identified a missing environment variable on the new release", "Roll back and re-release with validated configuration", "Validate required environment variables before deploy"),
    ("deployment", "Catalog Frontend", "Static assets returned 404 after deployment", "HTTP 404", "CDN cache invalidation and asset manifest versioning were out of sync", "HTML referenced old filenames no longer present in object storage", "Restore the matching asset bundle and invalidate the affected CDN paths", "Use immutable asset names and atomic deployment manifests"),
    ("deployment", "Reports Scheduler", "Jobs stopped firing after configuration update", "CRON-MISS", "A timezone default changed from UTC to local time", "Job history showed schedules shifted by several hours without execution errors", "Correct timezone configuration and backfill missed jobs", "Use explicit UTC schedules and tests for timezone changes"),
    ("network", "Public API Edge", "Some users could not reach the API", "DNS-SERVFAIL", "An authoritative DNS record was accidentally removed during zone editing", "Resolver traces showed SERVFAIL from a subset of caching resolvers", "Restore the record and verify propagation across resolvers", "Require zone change reviews and automated DNS checks"),
    ("network", "Internal Service Mesh", "Connection resets between internal services", "ECONNRESET", "An overly aggressive idle timeout on a proxy closed reused connections", "Proxy metrics showed rising idle-connection closes before upstream resets", "Align proxy and client keepalive/idle timeout settings", "Test connection reuse behavior under load"),
    ("network", "Partner API Integration", "TLS handshakes began failing", "TLS-HANDSHAKE", "A certificate rotation omitted the required intermediate certificate", "Handshake diagnostics showed an incomplete server certificate chain", "Deploy the complete certificate chain and verify TLS clients", "Automate certificate-chain checks before rotation"),
    ("auth", "Employee SSO", "Login attempts failed for many users", "OIDC-INVALID-ISSUER", "Identity-provider issuer URL changed without updating relying-party configuration", "OIDC discovery and application issuer settings no longer matched", "Update issuer configuration and verify token validation", "Contract-test identity-provider changes in staging"),
    ("auth", "Mobile Application", "Users received repeated 401 errors", "HTTP 401", "Client clock skew caused valid tokens to appear expired", "Rejected token timestamps disagreed with device and server clock measurements", "Correct time synchronization behavior and expand allowable clock skew safely", "Monitor authentication failures by device clock offset"),
]

CATEGORIES = {"database", "api", "cloud", "deployment", "network", "auth"}
REQUIRED = ["incident_id", "title", "date", "affected_service", "severity", "category", "symptoms", "error_codes", "timeline", "root_cause", "resolution", "preventive_actions", "source_type", "source_url", "full_report"]


def build_report(index: int, scene: tuple[str, ...]) -> dict:
    category, service, symptoms, code, cause, signal, fix, prevention = scene
    when = date(2025, 1, 10) + timedelta(days=index * 22)
    start = datetime.combine(when, datetime.min.time(), tzinfo=timezone.utc).replace(hour=9, minute=15)
    timeline = [
        {"time": (start).isoformat(), "event": f"Monitoring detected: {symptoms}."},
        {"time": (start + timedelta(minutes=9)).isoformat(), "event": f"On-call reviewed telemetry. {signal}."},
        {"time": (start + timedelta(minutes=27)).isoformat(), "event": f"Investigation identified: {cause}."},
        {"time": (start + timedelta(minutes=45)).isoformat(), "event": f"Mitigation implemented: {fix}."},
        {"time": (start + timedelta(minutes=63)).isoformat(), "event": "Key service metrics recovered; on-call confirmed stabilization."},
    ]
    incident_id = f"SYN-{index:03d}"
    title = f"{service}: {symptoms.split(' and ')[0]}"
    severity = "SEV-1" if index in {1, 6, 12, 16} else "SEV-2" if index % 3 else "SEV-3"
    narrative = (
        f"# {incident_id} — {title}\n\n"
        f"Date: {when.isoformat()} | Severity: {severity} | Service: {service} | Category: {category}\n\n"
        f"## Impact and symptoms\nA fictional production incident affected {service}. Operators observed {symptoms}. "
        f"The most useful error signature was {code}; this alone does not establish the cause.\n\n"
        f"## Investigation evidence\n{signal}. The team compared changes, service telemetry, and logs before narrowing down the fault.\n\n"
        f"## Timeline\n" + "\n".join(f"- {e['time']}: {e['event']}" for e in timeline) + "\n\n"
        f"## Confirmed historical root cause\n{cause}. In this fictional scenario, the evidence above supports this cause.\n\n"
        f"## Mitigation and resolution\n{fix}. Teams verified recovery using the originally affected service metrics.\n\n"
        f"## Prevention\n{prevention}.\n\n"
        "## Dataset note\nSYNTHETIC TEST DATA: this event, its timestamps, and its technical narrative are fictional."
    )
    return {
        "incident_id": incident_id, "title": title, "date": when.isoformat(),
        "affected_service": service, "severity": severity, "category": category,
        "symptoms": symptoms, "error_codes": [code], "timeline": timeline,
        "root_cause": cause, "resolution": fix, "preventive_actions": [prevention],
        "source_type": "synthetic", "source_url": None,
        "publisher": None, "source_title": None,
        "collected_at": datetime.now(timezone.utc).isoformat(), "full_report": narrative,
    }


def generate() -> None:
    SYNTHETIC.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for n, scenario in enumerate(SCENARIOS, start=1):
        path = SYNTHETIC / f"SYN-{n:03d}.json"
        if path.exists():
            print(f"Keeping existing {path.name} (no overwrite)")
            continue
        path.write_text(json.dumps(build_report(n, scenario), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Synthetic dataset folder: {SYNTHETIC}")
    print("Public reports were NOT fabricated or downloaded. Add verified JSON records to:", PUBLIC)


def validate() -> bool:
    BASE.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    files = sorted(SYNTHETIC.glob("*.json")) + sorted(PUBLIC.glob("*.json"))
    records = []
    errors = []
    ids = set()
    sources = set()
    missing = Counter()
    for path in files:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        if not isinstance(item, dict):
            errors.append(f"{path}: expected a JSON object")
            continue
        for field in REQUIRED:
            if field not in item or item[field] in ("", [], {}):
                missing[field] += 1
                if field not in {"source_url"}:
                    errors.append(f"{path.name}: missing {field}")
        identifier = item.get("incident_id")
        if identifier in ids:
            errors.append(f"{path.name}: duplicate incident ID {identifier}")
        ids.add(identifier)
        source_type = item.get("source_type")
        if source_type not in {"synthetic", "public"}:
            errors.append(f"{path.name}: invalid source_type")
        if (path.parent == SYNTHETIC and source_type != "synthetic") or (path.parent == PUBLIC and source_type != "public"):
            errors.append(f"{path.name}: source_type and folder disagree")
        if item.get("category") not in CATEGORIES:
            errors.append(f"{path.name}: unknown category {item.get('category')}")
        if source_type == "public":
            url = item.get("source_url")
            if not isinstance(url, str) or not re.match(r"^https?://", url):
                errors.append(f"{path.name}: public reports require a source URL")
            elif url in sources:
                errors.append(f"{path.name}: duplicate public source URL {url}")
            sources.add(url)
            if not item.get("publisher") or not item.get("source_title"):
                errors.append(f"{path.name}: public reports require publisher and source_title")
        else:
            if item.get("source_url") is not None:
                errors.append(f"{path.name}: synthetic reports must use source_url=null")
        records.append(item)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(records), "synthetic": sum(x.get("source_type") == "synthetic" for x in records),
        "public": sum(x.get("source_type") == "public" for x in records),
        "categories": dict(sorted(Counter(x.get("category", "unknown") for x in records).items())),
        "missing_field_counts": dict(sorted(missing.items())),
        "validation_errors": errors,
        "note": "Synthetic incidents are fiction. Public records must be independently sourced and verified.",
    }
    REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Saved:", REPORT)
    return not errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["generate", "validate", "all"], default="all")
    args = parser.parse_args()
    if args.command in ("generate", "all"):
        generate()
    if args.command in ("validate", "all"):
        if not validate():
            raise SystemExit(1)


if __name__ == "__main__":
    main()
