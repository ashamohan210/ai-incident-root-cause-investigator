"""Approved bounded Tavily discovery/extraction; source review is a separate step."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from tavily import TavilyClient
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/collection"
QUERIES = [
    "engineering database outage postmortem root cause GitLab GitHub",
    "API microservices outage postmortem root cause engineering",
    "Cloudflare cloud infrastructure outage postmortem",
    "Kubernetes outage postmortem engineering root cause",
    "GitHub deployment configuration outage incident postmortem",
    "Cloudflare DNS network outage postmortem",
    "authentication login outage postmortem engineering",
]
DOMAINS = ["blog.cloudflare.com", "github.blog", "about.gitlab.com", "slack.engineering", "engineering.atspotify.com", "discord.com", "dropbox.tech", "engineering.atmeta.com"]


def canonical(url):
    p = urlsplit(url)
    return urlunsplit(("https", p.netloc.lower(), p.path.rstrip("/"), "", ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved", action="store_true", help="Explicit approval for this 13-credit run")
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Review the 7-search/6-extract, 13-credit plan and pass --approved only with approval.")
    OUT.mkdir(parents=True, exist_ok=True)
    ledger_path = OUT / "usage.json"
    if ledger_path.exists():
        raise SystemExit("This run already has a ledger. No additional API calls made; review saved results.")
    load_dotenv(ROOT / ".env", override=False)
    if not os.getenv("TAVILY_API_KEY"):
        raise SystemExit("Set TAVILY_API_KEY in local .env; do not paste it into chat.")
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"], session=session)
    ledger = {"limit_credits": 13, "reserved_credits": 0, "reported_credits": 0,
              "search_calls": 0, "extract_calls": 0, "calls": []}

    def call(kind, **kwargs):
        if ledger["reserved_credits"] + 1 > 13 or ledger[kind + "_calls"] >= (7 if kind == "search" else 6):
            raise RuntimeError("Approved budget exhausted")
        ledger["reserved_credits"] += 1
        ledger[kind + "_calls"] += 1
        entry = {"kind": kind, "reserved": 1, "status": "pending"}
        ledger["calls"].append(entry)
        ledger_path.write_text(json.dumps(ledger, indent=2))
        # Reserve before transmission. No retries; ambiguous failures stop the run.
        result = getattr(client, kind)(include_usage=True, **kwargs)
        (OUT / f"{kind}-{ledger[kind + '_calls']:02d}.json").write_text(json.dumps(result, indent=2))
        usage = result.get("usage", {})
        credits = usage.get("credits")
        entry.update(status="complete", usage=usage)
        if not isinstance(credits, (int, float)) or credits < 0 or credits > 1:
            entry["status"] = "usage_unconfirmed_stop"
            ledger_path.write_text(json.dumps(ledger, indent=2))
            raise RuntimeError("Unexpected or missing usage; stopped before another call")
        ledger["reported_credits"] += credits
        ledger_path.write_text(json.dumps(ledger, indent=2))
        return result

    candidates = {}
    for query in QUERIES:
        result = call("search", query=query, search_depth="basic", max_results=8,
                      include_domains=DOMAINS, auto_parameters=False, include_answer=False,
                      include_raw_content=False)
        for row in result.get("results", []):
            url = row.get("url", "")
            if urlsplit(url).hostname not in DOMAINS:
                continue
            key = canonical(url)
            candidates.setdefault(key, row)
    # Prefer incident-specific titles; exclude indexes, roundup pages, and marketing.
    terms = ("outage", "postmortem", "post-mortem", "incident", "disruption", "downtime")
    selected = [row for row in candidates.values() if any(t in row.get("title", "").lower() for t in terms)][:30]
    (OUT / "candidates.json").write_text(json.dumps(selected, indent=2))
    for start in range(0, len(selected), 5):
        call("extract", urls=[r["url"] for r in selected[start:start + 5]],
             extract_depth="basic", format="markdown", include_images=False)
    print(json.dumps(ledger, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Collection stopped. Inspect data/collection/usage.json and saved responses; no automatic retry was made.", file=sys.stderr)
        sys.exit(1)
