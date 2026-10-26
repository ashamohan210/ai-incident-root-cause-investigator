"""Explicit one-time official-model download; ordinary searches stay offline."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.incident_investigator.retrieval import retrieval_config
from src.incident_investigator.providers import ROOT

if __name__ == "__main__":
    from huggingface_hub import HfApi, snapshot_download
    cfg = retrieval_config()
    path = ROOT / cfg["reranker_path"]
    revision = HfApi(token=False).model_info(cfg["reranker_model"]).sha
    snapshot_download(cfg["reranker_model"], revision=revision, local_dir=path, token=False,
        allow_patterns=["config.json", "model.safetensors", "tokenizer*", "vocab.txt", "special_tokens_map.json"])
    manifest = {"model": cfg["reranker_model"], "revision": revision,
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}}
    (path / "download_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"model": cfg["reranker_model"], "revision": revision, "downloaded": True}))
