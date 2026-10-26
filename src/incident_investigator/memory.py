"""Hosted Mem0 adapter: explicit user facts, composite scopes, bounded calls."""
import hashlib
import json
import os
import re
import tomllib
import uuid
import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import httpx

from .providers import ROOT


class MemoryUnavailable(RuntimeError):
    pass


def memory_config():
    return tomllib.loads((ROOT / "config/memory.toml").read_text())


def memory_enabled():
    """Fail closed unless the optional integration is explicitly enabled."""
    return memory_config().get("enabled") is True


def require_memory_enabled():
    if not memory_enabled():
        raise MemoryUnavailable("Persistent memory is disabled in config/memory.toml.")


@dataclass(frozen=True)
class Scope:
    user_id: str
    investigation_id: str
    session_id: str

    def __post_init__(self):
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) for value in (self.user_id, self.investigation_id, self.session_id)):
            raise ValueError("Use stable, pseudonymous scope IDs (letters, digits, underscores, hyphens).")

    @property
    def entity(self):
        return "rca_" + hashlib.sha256(f"{self.user_id}\0{self.investigation_id}".encode()).hexdigest()


class UsageGuard:
    """Journal reservations before HTTP transmission. No retries or deletions."""
    def __init__(self, path=None):
        self.path = Path(path or ROOT / memory_config()["ledger_path"])

    def snapshot(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"reads": 0, "writes": 0, "connectivity_checks": 0, "deletions": 0, "calls": [],
                "credit_usage": "Not reported by these memory endpoints; confirm in Mem0 dashboard."}

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def before(self, request):
        require_memory_enabled()
        path, method = request.url.path, request.method
        if method == "GET" and path == "/v1/ping/":
            kind = "connectivity_checks"
        elif method == "POST" and path == "/v3/memories/":
            body = json.loads(request.content)
            if not str(body.get("filters", {}).get("user_id", "")).startswith("rca_"):
                raise MemoryUnavailable("Unscoped memory read blocked")
            kind = "reads"
        elif (method == "POST" and path == "/v3/memories/add/") or method == "PUT" and path.startswith("/v1/memories/"):
            kind = "writes"
        else:
            raise MemoryUnavailable("Unapproved Mem0 endpoint/method blocked (including deletion).")
        with self.locked():
            ledger = self.snapshot()
            limit = memory_config()["max_read_operations"] if kind == "reads" else memory_config()["max_write_operations"]
            if kind != "connectivity_checks" and ledger[kind] >= limit:
                raise MemoryUnavailable("Approved Mem0 operation budget exhausted.")
            ledger[kind] += 1
            identifier = uuid.uuid4().hex
            request.extensions["memory_meter_call_id"] = identifier
            ledger["calls"].append({"id": identifier, "kind": kind, "method": method, "endpoint": path,
                                    "at": datetime.now(timezone.utc).isoformat(), "status": "reserved"})
            self.path.write_text(json.dumps(ledger, indent=2))

    def after(self, response):
        with self.locked():
            ledger = self.snapshot()
            identifier = response.request.extensions.get("memory_meter_call_id")
            match = next((c for c in ledger["calls"] if c.get("id") == identifier), None)
            if match is not None:
                match["status"] = response.status_code
            self.path.write_text(json.dumps(ledger, indent=2))


def platform_client(guard=None):
    require_memory_enabled()
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("MEM0_API_KEY", "").strip():
        raise MemoryUnavailable("MEM0_API_KEY is not configured; persistent memory unavailable.")
    os.environ["MEM0_TELEMETRY"] = "false"
    os.environ.setdefault("MEM0_DIR", str(ROOT / "data/mem0_sdk"))
    from mem0 import MemoryClient
    guard = guard or UsageGuard()
    transport = httpx.HTTPTransport(retries=0)
    client = httpx.Client(transport=transport, timeout=memory_config()["timeout_seconds"],
                          event_hooks={"request": [guard.before], "response": [guard.after]})
    try:
        return MemoryClient(api_key=os.environ["MEM0_API_KEY"], client=client)
    except Exception:
        client.close()
        raise MemoryUnavailable("Mem0 connection failed; persistent memory unavailable. No automatic retry.") from None


KINDS = {"incident_description", "affected_service", "symptom", "completed_check", "ruled_out", "user_fact", "decision", "open_question"}


def safe_text(text):
    if not isinstance(text, str) or not text.strip() or len(text) > memory_config()["max_text_chars"]:
        raise ValueError("Memory text must be non-empty and at most 2000 characters.")
    if re.search(r"(?i)(api[_ -]?key|password|authorization|bearer\s|private.key|secret\s*[:=])", text):
        raise ValueError("Potential credentials must not be stored in memory.")
    if any(value and len(value) > 8 and value in text for key, value in os.environ.items() if key.endswith("API_KEY")):
        raise ValueError("Credential value detected; memory rejected.")
    return text.strip()


class InvestigationMemory:
    def __init__(self, sdk=None):
        self.sdk = sdk if sdk is not None else platform_client()
        self.receipts = ROOT / "data/memory/write_receipts.json" if sdk is None else None

    def _scope_ok(self, row, scope):
        metadata = row.get("metadata") or {}
        return (row.get("user_id", scope.entity) == scope.entity and metadata.get("scope_entity") == scope.entity and metadata.get("app") == "incident_rca" and
                metadata.get("user_id") == scope.user_id and metadata.get("investigation_id") == scope.investigation_id and
                bool(metadata.get("session_id")) and metadata.get("authority") == "user_reported")

    def retrieve(self, scope):
        require_memory_enabled()
        rows = []
        for page in range(1, 4):
            try:
                response = self.sdk.get_all(filters={"user_id": scope.entity}, page=page, page_size=memory_config()["page_size"])
            except Exception:
                raise MemoryUnavailable("Mem0 read failed; persistent memory unavailable. No automatic retry.") from None
            if not isinstance(response, dict) or not isinstance(response.get("results"), list):
                raise MemoryUnavailable("Mem0 returned an unsupported memory response.")
            for row in response["results"]:
                if not self._scope_ok(row, scope):
                    raise MemoryUnavailable("Memory scope validation failed; all returned memory was discarded.")
                rows.append(row)
            if len(rows) > memory_config()["max_memories"]:
                raise MemoryUnavailable("Investigation memory limit exceeded; no partial context used.")
            if not response.get("next"):
                break
        else:
            raise MemoryUnavailable("Memory pagination limit reached; no partial context used.")
        latest = {}
        for row in rows:
            metadata = row["metadata"]
            key = (metadata["kind"], metadata["fact_key"])
            if key not in latest or (metadata.get("recorded_at", ""), row["id"]) > (latest[key]["metadata"].get("recorded_at", ""), latest[key]["id"]):
                latest[key] = row
        return list(latest.values())

    def add_fact(self, scope, kind, text, fact_key=None, supersedes=None):
        require_memory_enabled()
        if kind not in KINDS:
            raise ValueError("Only user-supplied investigation facts are allowed; AI hypotheses are not memory facts.")
        text = safe_text(text)
        fact_key = fact_key or hashlib.sha256(text.casefold().encode()).hexdigest()
        existing = self.retrieve(scope)
        if supersedes and not any(row["id"] == supersedes for row in existing):
            raise ValueError("Cannot supersede a memory outside the validated investigation scope.")
        same = next((r for r in existing if r["metadata"]["kind"] == kind and r["metadata"]["fact_key"] == fact_key), None)
        if same and same["memory"] == text:
            return {"status": "duplicate_skipped", "id": same["id"]}
        metadata = {"app": "incident_rca", "authority": "user_reported", "user_id": scope.user_id,
                    "scope_entity": scope.entity,
                    "investigation_id": scope.investigation_id, "session_id": scope.session_id,
                    "kind": kind, "fact_key": fact_key, "recorded_at": datetime.now(timezone.utc).isoformat()}
        if supersedes:
            metadata["supersedes"] = supersedes
        operation = hashlib.sha256(json.dumps([scope.entity, kind, fact_key, text]).encode()).hexdigest()
        metadata["operation_key"] = operation
        receipts = {}
        if self.receipts is not None:
            if self.receipts.exists():
                receipts = json.loads(self.receipts.read_text())
            if operation in receipts:
                raise MemoryUnavailable("This write was already submitted; its outcome is not visible yet. Read later instead of duplicating it.")
            receipts[operation] = "submitted_outcome_unconfirmed"
            self.receipts.parent.mkdir(parents=True, exist_ok=True)
            self.receipts.write_text(json.dumps(receipts, indent=2))
        try:
            response = self.sdk.add([{"role": "user", "content": text}], user_id=scope.entity,
                                    metadata=metadata, infer=False)
        except Exception:
            raise MemoryUnavailable("Mem0 write failed or outcome is uncertain; no automatic retry. Read before retrying.") from None
        if response.get("status") in {"PENDING", "QUEUED"} or response.get("event_id"):
            return {"status": "queued", "event_id": response.get("event_id"),
                    "note": "Verify persistence with a subsequent scoped read; do not retry this write automatically."}
        return {"status": "stored", "response": response}

    def create_investigation(self, scope, description):
        return self.add_fact(scope, "incident_description", description, fact_key="incident_description")

    def supersede(self, scope, memory_id, text):
        row = next((r for r in self.retrieve(scope) if r["id"] == memory_id), None)
        if row is None:
            raise ValueError("Memory ID does not belong to this user/investigation.")
        return self.add_fact(scope, row["metadata"]["kind"], text, fact_key=row["metadata"]["fact_key"], supersedes=memory_id)

    def clear_investigation(self, scope, approved=False):
        # This approved phase explicitly forbids ALL remote deletion. A future
        # separately reviewed deletion adapter must validate each ID, never bulk-delete.
        raise MemoryUnavailable("Remote deletion is disabled in this phase, even with a CLI flag. Separate explicit approval is required.")


def confirmed_facts(description):
    """Conservative verbatim extraction; never parse assistant output."""
    facts = []
    for sentence in re.split(r"(?<=[.!?])\s+", description.strip()):
        if re.search(r"(?i)\bwe (?:have )?checked\b", sentence):
            facts.append({"kind": "completed_check", "text": sentence})
        elif re.search(r"(?i)\bwe confirmed\b.+\b(?:is not|was not|ruled out)\b", sentence):
            facts.append({"kind": "ruled_out", "text": sentence})
    return facts
