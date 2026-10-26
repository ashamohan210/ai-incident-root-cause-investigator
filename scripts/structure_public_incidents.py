"""Build reviewed public records from saved Tavily responses; never calls APIs."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reviewed primary incident reports. Analyst categories are explicitly labeled.
# Missing dates or source fields stay null; no model-generated facts are used.
REVIEWED = {
    "postmortem-of-database-outage-of-january-31": ("database", "2017-01-31"),
    "post-mortem-on-cloudflare-control-plane-and-analytics-outage": ("cloud", "2023-11-02"),
    "18-november-2025-outage": ("deployment", "2025-11-18"),
    "5-december-2025-outage": ("deployment", "2025-12-05"),
    "cloudflare-service-outage-june-12-2025": ("cloud", "2025-06-12"),
    "deep-dive-into-cloudflares-sept-12-dashboard-and-api-outage": ("api", "2025-09-12"),
    "cloudflare-incident-on-february-6-2025": ("cloud", "2025-02-06"),
    "cloudflare-incident-march-21-2025": ("auth", "2025-03-21"),
    "dns-outage-post-mortem": ("network", None),
    "oct21-post-incident-analysis": ("database", "2018-10-21"),
    "the-august-17-outage-and-the-work-ahead": ("cloud", None),
    "todays-outage-post-mortem-82515": ("network", None),
    "cloudflare-1-1-1-1-incident-on-july-14-2025": ("network", "2025-07-14"),
    "incident-report-spotify-outage-on-march-8": ("cloud", "2022-03-08"),
}


def article_text(raw):
    start = re.search(r"^# .+", raw, re.M)
    if not start:
        raise ValueError("Missing article title")
    text = raw[start.start():]
    text = re.split(r"^## (?:Related tags|Written by|More to explore|Subscribe|Troubleshooting FAQ)|^### Related articles", text, maxsplit=1, flags=re.M)[0]
    text = re.sub(r"!\[[^\]]*\]\([^\n]*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^This post is also available.*$", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def section(text, pattern):
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.M)
    for part in sections:
        heading = part.splitlines()[0] if part else ""
        if re.search(pattern, heading, re.I):
            return part.strip()
    return None


def main():
    output = ROOT / "data/incidents/public"
    output.mkdir(parents=True, exist_ok=True)
    seen, accepted, rejected = set(), [], []
    for path in sorted((ROOT / "data/collection").glob("extract-*.json")):
        for result in json.loads(path.read_text()).get("results", []):
            url = result["url"]
            slug = urlsplit(url).path.rstrip("/").split("/")[-1]
            if slug not in REVIEWED or slug in seen:
                rejected.append({"url": url, "reason": "duplicate/alias" if slug in seen else "not a reviewed primary single-incident report"})
                continue
            text = article_text(result["raw_content"])
            if len(text) < 800:
                rejected.append({"url": url, "reason": "insufficient incident content"})
                continue
            seen.add(slug)
            category, date = REVIEWED[slug]
            identifier = "PUB-" + hashlib.sha256(slug.encode()).hexdigest()[:12]
            host = urlsplit(url).hostname
            publisher = {"blog.cloudflare.com": "Cloudflare", "github.blog": "GitHub", "about.gitlab.com": "GitLab", "engineering.atspotify.com": "Spotify"}[host]
            # Fields are verbatim source sections, not inferred explanations.
            record = {"incident_id": identifier, "title": text.splitlines()[0].lstrip("# "),
                      "incident_date": date, "affected_service": None, "severity": None,
                      "category": category, "category_basis": "analyst classification",
                      "symptoms": None, "error_codes": None,
                      "impact": section(text, r"impact|what was impacted"),
                      "timeline": section(text, r"timeline"),
                      "root_cause": section(text, r"root cause analysis|technical description|analysis$|what happened"),
                      "resolution": section(text, r"^#+ (resolution|incident response|how we responded|restoring|recovering)"),
                      "preventive_actions": section(text, r"remediation|next steps|going forward|lessons|improving recovery|where do we go|what we.re doing|what we have done"),
                      "source_type": "public", "source_url": url, "publisher": publisher,
                      "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                      "full_report": text, "evidence_format": "verbatim source sections; null means no mapped source section",
                      "reuse_note": "Private educational source evidence; no redistribution license asserted. Follow original publisher terms.",
                      "extraction_source": path.relative_to(ROOT).as_posix()}
            target = output / (identifier + ".json")
            if not target.exists():
                target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
            accepted.append({"incident_id": identifier, "url": url})
    report = {"accepted": accepted, "rejected": rejected}
    (ROOT / "data/collection/review.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"public_reports": len(accepted), "rejected_or_duplicate_pages": len(rejected)}, indent=2))


if __name__ == "__main__":
    main()
