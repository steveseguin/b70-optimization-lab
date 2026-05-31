#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$ROOT/configs/reap.env"
set +a

"$VENV/bin/python" - <<'PY'
import json
from huggingface_hub import HfApi, hf_hub_download

import os

repo = os.environ["REAP_MINIMAX_REPO"]
api = HfApi()
info = api.model_info(repo, files_metadata=True)
files = info.siblings or []
total = sum((f.size or 0) for f in files)
safe = sum((f.size or 0) for f in files if f.rfilename.endswith(".safetensors"))
config_path = hf_hub_download(repo, "config.json", cache_dir=os.environ["HF_HOME"])
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
q = config.get("quantization_config", {})
record = {
    "repo": info.id,
    "private": info.private,
    "gated": getattr(info, "gated", None),
    "sha": info.sha,
    "last_modified": info.last_modified.isoformat() if info.last_modified else None,
    "tags": info.tags,
    "file_count": len(files),
    "total_bytes": total,
    "safetensors_bytes": safe,
    "total_gib": round(total / 1024**3, 2),
    "safetensors_gib": round(safe / 1024**3, 2),
    "architectures": config.get("architectures"),
    "model_type": config.get("model_type"),
    "hidden_size": config.get("hidden_size"),
    "num_hidden_layers": config.get("num_hidden_layers"),
    "num_local_experts": config.get("num_local_experts"),
    "num_experts_per_tok": config.get("num_experts_per_tok"),
    "intermediate_size": config.get("intermediate_size"),
    "max_position_embeddings": config.get("max_position_embeddings"),
    "quantization": {
        "quant_method": q.get("quant_method"),
        "packing_format": q.get("packing_format"),
        "bits": q.get("bits"),
        "group_size": q.get("group_size"),
        "sym": q.get("sym"),
    },
}
print(json.dumps(record, indent=2, sort_keys=True))
PY
