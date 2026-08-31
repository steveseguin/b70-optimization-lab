#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
attempt_runner=${script_dir}/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh
campaign=qwen38-autoround-detpad-mtp0-local-tp2-20260830-r3
out_parent=/mnt/fast-ai/bench-results
cache_parent=/mnt/fast-ai/vllm-cache
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r3-prereg.md
r2_prefix=${out_parent}/qwen38-autoround-detpad-mtp0-local-tp2-20260830-r2

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "$prereg" && -x "$attempt_runner" ]] || fail 'missing preregistration or attempt runner'
[[ -d "$model" && ! -L "$model" ]] || fail 'model must be a real local directory'
[[ "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be on ext4'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
printf '%s  %s\n' \
  216efe21ec193ed50fc3fa453fcf2161c864aac5431d579ece24a35e5dc05d2a "${r2_prefix}-eager-oracle/performance.json" \
  3a8ffa399c64d3a34d8703eb2a9f4cee2d2076cef8d7b79d74c822953914f6ed "${r2_prefix}-compiled-A/performance.json" \
  | sha256sum -c -
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

common=(
  IMAGE="$image"
  EXPECTED_IMAGE_ID="$image_id"
  EXPECTED_XPU_EXTENSION_SHA256=c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620
  EXPECTED_GDN_LIBRARY_SHA256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
  MODEL_DIR="$model"
  GPU_IDS=0,1
  MIN_HOST_MEMORY_GIB=8
  CONTAINER_MEMORY=12g
  CONTAINER_MEMORY_SWAP=36g
)

run_arm() {
  local mode=$1 label=$2 port=$3
  env "${common[@]}" EXECUTION_MODE="$mode" ATTEMPT="$label" \
    OUT_DIR="${out_parent}/${campaign}-${label}" \
    VLLM_CACHE_DIR="${cache_parent}/${campaign}-${label}" PORT="$port" \
    "$attempt_runner"
}

run_arm eager eager-B 18164
run_arm compiled compiled-B 18165

python3 - "$r2_prefix" "${out_parent}/${campaign}" "$prereg" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

r2, r3, prereg = sys.argv[1:]
paths = {
    "r2_eager": pathlib.Path(r2 + "-eager-oracle/performance.json"),
    "r2_compiled": pathlib.Path(r2 + "-compiled-A/performance.json"),
    "r3_eager": pathlib.Path(r3 + "-eager-B/performance.json"),
    "r3_compiled": pathlib.Path(r3 + "-compiled-B/performance.json"),
}

def load(path):
    value = json.loads(path.read_text())
    return value, {row["prompt_id"]: row["token_ids"] for row in value["rows"]}

loaded = {name: load(path) for name, path in paths.items()}

def compare(left, right):
    a, b = loaded[left][1], loaded[right][1]
    prompts = sorted(set(a) | set(b))
    exact = [prompt for prompt in prompts if a.get(prompt) == b.get(prompt)]
    return {"exact": len(exact), "total": len(prompts),
            "mismatching_prompt_ids": [p for p in prompts if p not in exact]}

comparisons = {
    "eager_repeat": compare("r2_eager", "r3_eager"),
    "compiled_repeat": compare("r2_compiled", "r3_compiled"),
    "r3_cross_mode": compare("r3_eager", "r3_compiled"),
}
if comparisons["eager_repeat"]["exact"] < 12:
    classification = "shared-or-eager-tp2-nondeterminism"
elif comparisons["compiled_repeat"]["exact"] < 12:
    classification = "compiled-tp2-nondeterminism"
elif comparisons["r3_cross_mode"]["exact"] < 12:
    classification = "repeatable-cross-mode-semantic-drift"
else:
    classification = "repeatable-and-cross-mode-exact"

metric_key = "class_balanced_tok_s_1_100_intervals_after_ttft"
result = {
    "schema": "neural.download.qwen38-autoround-determinism-localization.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": pathlib.Path(r3).name,
    "classification": classification,
    "comparisons": comparisons,
    "class_balanced_median_tok_s": {
        name: value[0]["summary"][metric_key]["median"]
        for name, value in loaded.items()
    },
    "performance_sha256": {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    },
    "preregistration": prereg,
    "preregistration_sha256": hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest(),
    "reporting_boundary": "Diagnostic localization only; no speed promotion or MTP authorization."
}
out = pathlib.Path(r3 + "-result.json")
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
PY
