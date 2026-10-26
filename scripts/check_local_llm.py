"""Bounded local LLM smoke test with sampled RSS and Ollama allocation metrics."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.providers import ROOT, llm_provider


def measure(call):
    stop = threading.Event()
    samples = []
    def swap():
        try:
            return subprocess.check_output(["sysctl", "vm.swapusage"], text=True).strip()
        except (OSError, subprocess.SubprocessError):
            return "unavailable"
    swap_before = swap()

    def sample():
        while not stop.is_set():
            try:
                output = subprocess.check_output(["ps", "-axo", "rss=,comm="], text=True)
                samples.append(sum(int(line.split()[0]) * 1024 for line in output.splitlines()
                                   if "ollama" in line.lower() and line.split()[0].isdigit()))
            except (OSError, subprocess.SubprocessError):
                pass
            stop.wait(0.5)

    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    started = time.monotonic()
    try:
        value = call()
    finally:
        stop.set(); worker.join(timeout=2)
    return value, {"wall_seconds": round(time.monotonic() - started, 3),
                   "system_swap_before": swap_before, "system_swap_after": swap(),
                   "sampled_peak_ollama_process_rss_bytes": max(samples) if samples else None,
                   "rss_sample_count": len(samples),
                   "memory_note": "RSS sums Ollama processes; Metal/unified-memory allocation may not be fully represented. api_ps separately reports model allocation."}


if __name__ == "__main__":
    provider = llm_provider()
    result, metrics = measure(lambda: provider.generate(
        'Return {"ready":true,"role":"local incident investigation"}.',
        {"type": "object", "properties": {"ready": {"type": "boolean"}, "role": {"type": "string"}}, "required": ["ready", "role"], "additionalProperties": False}))
    parsed = json.loads(result)
    if parsed.get("ready") is not True:
        raise SystemExit("Local model smoke test failed; stop before investigations.")
    metrics.update(model=provider.model, generation=provider.last_metrics,
                   api_ps=provider.transport.request("/api/ps"), smoke_response=parsed)
    path = ROOT / "data/processed/phase6_model_smoke.json"
    path.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
