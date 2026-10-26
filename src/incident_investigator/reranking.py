"""Optional CPU cross-encoder, loaded only from explicitly downloaded local files."""
import math
import json
from functools import lru_cache

from .providers import ROOT


@lru_cache(maxsize=1)
def load_model(path):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        path, local_files_only=True, trust_remote_code=False, use_safetensors=True)
    model.to("cpu").eval()
    return tokenizer, model


def rerank(query, candidates, cfg):
    """Score query/passage pairs; windows retain long passage tails."""
    if not cfg["reranking_enabled"]:
        return candidates, {"active": False, "reason": "disabled in configuration"}
    if not candidates:
        return candidates, {"active": False, "reason": "no candidates"}
    try:
        import torch
        path = ROOT / cfg["reranker_path"]
        if not (path / "model.safetensors").exists():
            raise RuntimeError("Local model files not installed")
        manifest = json.loads((path / "download_manifest.json").read_text())
        if manifest.get("model") != cfg["reranker_model"] or not manifest.get("revision"):
            raise ValueError("Local reranker identity does not match configuration")
        tokenizer, model = load_model(str(path))
        if len(tokenizer.encode(query, add_special_tokens=False)) > 128:
            raise ValueError("Query too long for configured reranker window")
        scored = []
        for candidate in candidates:
            tokens = tokenizer(query, candidate["chunk_text"], padding=True,
                truncation="only_second", max_length=512, stride=64,
                return_overflowing_tokens=True, return_tensors="pt")
            tokens.pop("overflow_to_sample_mapping", None)
            with torch.inference_mode():
                score = float(model(**tokens).logits.reshape(-1).max().item())
            if not math.isfinite(score):
                raise ValueError("Non-finite reranker score")
            scored.append({**candidate, "rerank_score": score})
        scored.sort(key=lambda row: (-row["rerank_score"], -row["rrf_score"], row["id"]))
        return scored, {"active": True, "model": cfg["reranker_model"], "revision": manifest["revision"], "device": "cpu", "max_window_tokens": 512, "window_overlap_tokens": 64}
    except Exception:
        return candidates, {"active": False, "reason": "Local reranker unavailable or inference failed; retained RRF ranking."}
