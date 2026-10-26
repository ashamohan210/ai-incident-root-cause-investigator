"""Streamlit presentation and session orchestration; backend logic stays in Phase 6/7."""
import hashlib
import os
import re
import time
import uuid
from urllib.parse import urlparse

import streamlit as st

from .investigation import investigate

DEMO_USER = "genacademy-demo-engineer"


def display_text(value):
    """Plain text only; never render retrieved text as executable HTML/Markdown."""
    text = str(value or "")
    for key, secret in os.environ.items():
        if key.endswith("API_KEY") and len(secret) > 8:
            text = text.replace(secret, "[credential removed]")
    return re.sub(r"(?i)(bearer\s+|(?:api[_ -]?key|password|secret)\s*[:=]\s*)\S+", r"\1[removed]", text)


def public_url(value):
    """Only credential-free HTTP(S) source links, never file/javascript URLs."""
    try:
        if display_text(value) != str(value or ""):
            return None
        parsed = urlparse(str(value or ""))
        return str(value) if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def new_workspace():
    return {"turns": [], "last_submitted": None, "notice": "", "description": "", "service": ""}


def initialize():
    state = st.session_state
    if "ui_session_id" not in state:
        state.ui_session_id = "session-" + uuid.uuid4().hex
        candidate = st.query_params.get("investigation", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", candidate):
            candidate = "incident-" + uuid.uuid4().hex[:12]
        state.active_investigation = candidate
        state.workspaces = {}
        state.busy = False
    if not state.get("session_only_ui"):
        for workspace in state.workspaces.values():
            workspace.pop("memories", None)
            workspace["notice"] = ""
        state.session_only_ui = True
    st.query_params["investigation"] = state.active_investigation
    return state.workspaces.setdefault(state.active_investigation, new_workspace())


def switch_investigation(investigation_id):
    """Switch only among this browser session's workspaces; no remote reads."""
    investigation_id = investigation_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", investigation_id):
        st.error("Use 1–100 letters, numbers, underscores, or hyphens for the investigation ID.")
        return
    state = st.session_state
    state.active_investigation = investigation_id
    st.query_params["investigation"] = investigation_id
    state.workspaces.setdefault(investigation_id, new_workspace())


def conversation_context(workspace):
    """Bounded user statements only; never feed generated conclusions back as facts."""
    turns = workspace["turns"]
    if not turns:
        return []
    initial = (("Affected service: " + workspace["service"] + ".\n") if workspace["service"] else "") + workspace["description"]
    context = [(initial or turns[0]["question"])[:2000]]
    for turn in turns[-2:]:
        question = turn["question"][:500]
        if turn.get("followup", turn is not turns[0]) and question not in context:
            context.append(question)
    return context


def submit(workspace, text, service="", followup=False):
    text, service = text.strip(), service.strip()
    if not text or len(text) > 3500 or len(service) > 120:
        st.error("Enter 1–3500 characters of incident text and at most 120 characters for the service.")
        return
    description = (f"Affected service: {service}.\n" if service and not followup else "") + text
    try:
        # Input screening happens before any paid read/write or generation call.
        if display_text(text) != text or re.search(r"(?i)(api[_ -]?key|password|authorization|bearer\s|private.key|secret\s*[:=])", text):
            raise ValueError("Potential credentials")
        if display_text(service) != service or re.search(r"(?i)(api[_ -]?key|password|authorization|bearer\s|private.key|secret\s*[:=])", service):
            raise ValueError("Potential credentials")
    except ValueError:
        st.error("Remove credentials or sensitive secrets from your input before submitting.")
        return
    fingerprint = hashlib.sha256((str(followup) + "\0" + description).encode()).hexdigest()
    if st.session_state.busy or fingerprint == workspace.get("last_submitted"):
        st.info("This request was already submitted. Its saved result is shown below; no calls were repeated.")
        return
    # Reserve before sending. An uncertain failure must not trigger an automatic retry.
    workspace["last_submitted"] = fingerprint
    st.session_state.busy = True
    started = time.monotonic()
    notice = ""
    try:
        with st.status("Investigating… historical retrieval and local reasoning may take about 70 seconds.", expanded=True) as progress:
            context = conversation_context(workspace) if followup else []
            result = investigate(description, session_context=context)
            duration = round(time.monotonic() - started, 3)
            workspace["turns"].append({"question": description, "followup": followup, "result": result, "duration_seconds": duration})
            if not followup:
                workspace.update(description=text, service=service)
            workspace["notice"] = notice
            progress.update(label=f"Investigation complete in {duration:.1f} seconds", state="complete", expanded=False)
    except Exception:
        workspace["notice"] = "Investigation could not complete. Check local Ollama, Pinecone configuration, and connectivity. No automatic retry was made."
        st.error(workspace["notice"])
    finally:
        st.session_state.busy = False


def source(row):
    incident_id, title = row.get("incident_id", "Unknown incident"), row.get("title", "Untitled")
    kind = row.get("source_type", "unknown")
    st.text(display_text(f"{incident_id} · {title} · {'Synthetic training example' if kind == 'synthetic' else 'Public report' if kind == 'public' else 'Unknown source type'}"))
    reference = row.get("source_url") or row.get("source_file") or row.get("source_reference") or row.get("source") or ""
    url = public_url(reference) if kind == "public" else None
    if url:
        st.link_button("Open original public report", url)
    else:
        st.text(display_text(reference))
    if row.get("chunk_id"):
        st.caption(display_text("Passage: " + row["chunk_id"]))


def render_report(result):
    report = result["report"]
    status = report.get("status")
    st.subheader("Investigation summary")
    if status == "investigation":
        st.success("Historical evidence was validated. The current root cause remains unconfirmed.")
    else:
        st.warning("Insufficient validated historical evidence. No current root cause is established.")
    st.text(display_text(report.get("message") or report.get("current_incident_summary")))
    warnings = report.get("retrieval_warnings", [])
    if warnings:
        st.warning("Historical retrieval was unavailable or partially degraded. Check Pinecone and local Ollama. This report may be incomplete.")
    st.subheader("Similar historical incidents")
    seen = set()
    for row in report.get("similar_historical_incidents", []):
        if row["incident_id"] not in seen:
            source(row)
            seen.add(row["incident_id"])
    if not seen:
        st.caption("No validated historical matches are presented.")
    for heading, key in (("Historical root causes", "historical_root_causes"), ("Documented historical resolutions", "previous_resolutions"), ("Historical observations", "historical_observations")):
        st.subheader(heading)
        if not report.get(key):
            st.caption("None established in this response.")
        for finding in report.get(key, []):
            with st.container(border=True):
                source(finding)
                st.text(display_text(finding["supporting_passage"]))
    st.subheader("Current hypotheses — unconfirmed")
    evidence = {r["id"]: {**r, "chunk_id": r["id"]} for r in result.get("retrieved_evidence", [])}
    checks = []
    for number, hypothesis in enumerate(report.get("current_incident_hypotheses", []), 1):
        st.text(display_text(f"{number}. {hypothesis['hypothesis']}"))
        for chunk_id in hypothesis.get("supporting_chunk_ids", []):
            if chunk_id in evidence:
                source(evidence[chunk_id])
        checks.extend(hypothesis.get("diagnostic_checks", []))
    if not report.get("current_incident_hypotheses"):
        st.caption("No supported hypothesis is presented.")
    st.subheader("Recommended diagnostic checks")
    checks.extend(report.get("general_diagnostic_guidance", []))
    for number, check in enumerate(dict.fromkeys(checks), 1):
        st.text(display_text(f"{number}. {check}"))
    with st.expander("Limitations and timing details"):
        for item in report.get("limitations_and_unknowns", []):
            st.text(display_text(item))
        issues = report.get("citation_validation_issues", [])
        if any("failed" in str(issue).lower() or "timed out" in str(issue).lower() for issue in issues):
            st.warning("Reasoning or evidence validation could not complete. Check that Ollama is running and the configured model is available. No conclusion was accepted.")
        elif issues:
            st.warning("Evidence or citation checks rejected this draft; unsupported claims were withheld.")
        for name, seconds in result.get("timings", {}).items():
            st.text(f"{name}: {seconds} s")
        st.caption("Session context contains user statements, not documentary evidence. Synthetic reports are fictional examples. Similarity does not confirm a cause.")


def render_app():
    st.set_page_config(page_title="AI Incident Root Cause Investigator", page_icon="🔎", layout="wide")
    workspace = initialize()
    st.title("AI Incident Root Cause Investigator")
    st.write("Find similar incidents, review documented fixes, and investigate possible causes with traceable evidence.")
    with st.sidebar:
        st.subheader("Local demo profile")
        st.text(DEMO_USER)
        st.caption("Shared demo identity, not secure authentication. Use only on your own Mac.")
        with st.form("session_investigation_form"):
            selected = st.text_input("Investigation ID", value=st.session_state.active_investigation, key="session_investigation_id", max_chars=100)
            opened = st.form_submit_button("Open session investigation", disabled=st.session_state.busy)
        if opened:
            switch_investigation(selected)
            workspace = st.session_state.workspaces[st.session_state.active_investigation]
        st.caption("Switch investigations within this session. A bookmarked ID does not restore conversation history.")
        st.text("Session: " + st.session_state.ui_session_id)
    investigation_id = st.session_state.active_investigation
    st.caption("Active investigation: " + investigation_id)
    if workspace["notice"]:
        st.info(display_text(workspace["notice"]))
    st.info("Conversation context lasts only for the current session and may disappear when it ends or the page is reloaded. Persistent memory is disabled.")
    # Per-investigation widget keys prevent a switch from inheriting another incident's inputs.
    st.session_state.setdefault("service_" + investigation_id, workspace["service"])
    st.session_state.setdefault("description_" + investigation_id, workspace["description"])
    with st.form("incident_form_" + investigation_id):
        service = st.text_input("Affected service", max_chars=120, key="service_" + investigation_id)
        description = st.text_area("Incident description", height=150, max_chars=3500, key="description_" + investigation_id,
                                   placeholder="Describe the errors, recent changes, and checks already performed. Do not include secrets.")
        st.caption("Runs use existing hybrid search, reranking, LangGraph, and local Ollama. Follow-ups use only user-written context from this session.")
        run = st.form_submit_button("Run investigation", type="primary", disabled=st.session_state.busy)
    if run:
        submit(workspace, description, service)
    if workspace["turns"]:
        st.subheader("Conversation")
        for turn in workspace["turns"][:-1]:
            with st.expander("Earlier turn"):
                st.text(display_text(turn["question"]))
                st.text("Result: " + turn["result"]["report"]["status"])
                st.caption(f"Duration: {turn['duration_seconds']:.1f} seconds")
        latest = workspace["turns"][-1]
        with st.chat_message("user"):
            st.text(display_text(latest["question"]))
        with st.chat_message("assistant"):
            st.caption(f"Duration: {latest['duration_seconds']:.1f} seconds")
            render_report(latest["result"])
    with st.form("followup_form_" + investigation_id, clear_on_submit=True):
        followup = st.text_input("Follow-up question", key="followup_" + investigation_id, max_chars=3500,
                                 placeholder="What checks have we already performed?")
        send = st.form_submit_button("Send follow-up", disabled=st.session_state.busy)
    if send:
        before = len(workspace["turns"])
        submit(workspace, followup, followup=True)
        if len(workspace["turns"]) > before:
            st.rerun()
