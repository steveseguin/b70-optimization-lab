#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
runner=${script_dir}/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh
campaign=qwen38-autoround-native-gdn-tp2-20260830-r6
parent=/mnt/fast-ai/bench-results
cache_parent=/mnt/fast-ai/vllm-cache
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-autoround-native-gdn-tp2-r6-prereg.md
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "$prereg" && -x "$runner" ]] || fail 'missing preregistration or runner'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

run_arm() {
  local label=$1 port=$2
  env EXECUTION_MODE=compiled ATTEMPT="$label" IMAGE="$image" \
    EXPECTED_IMAGE_ID="$image_id" \
    EXPECTED_XPU_EXTENSION_SHA256=c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620 \
    EXPECTED_GDN_LIBRARY_SHA256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355 \
    EXPECTED_XPU_COMMUNICATOR_SHA256=5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d \
    GDN_NATIVE_FALLBACK=0 \
    MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround \
    GPU_IDS=0,1 MIN_HOST_MEMORY_GIB=8 CONTAINER_MEMORY=12g CONTAINER_MEMORY_SWAP=36g \
    OUT_DIR="${parent}/${campaign}-${label}" \
    VLLM_CACHE_DIR="${cache_parent}/${campaign}-${label}" PORT="$port" \
    "$runner"
}

run_arm native-A 18168
run_arm native-B 18169

python3 - "$parent" "$campaign" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

parent, campaign, prereg, image, image_id = sys.argv[1:]
parent = pathlib.Path(parent)

def load(label):
    root = parent / f"{campaign}-{label}"
    perf = json.loads((root / "performance.json").read_text())
    qual = json.loads((root / "qualification.json").read_text())
    rows = {row["prompt_id"]: row["token_ids"] for row in perf["rows"]}
    return root, perf, qual, rows

a, b = load("native-A"), load("native-B")
prompts = sorted(set(a[3]) | set(b[3]))
bad = [prompt for prompt in prompts if a[3].get(prompt) != b[3].get(prompt)]
exact = len(prompts) - len(bad)
metric = "class_balanced_tok_s_1_100_intervals_after_ttft"
passed = a[2]["status"] == b[2]["status"] == "passed" and exact == 12
result = {
    "schema": "neural.download.qwen38-autoround-native-gdn-repeat.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": campaign,
    "classification": "candidate-deterministic-parent" if passed else "failed-native-gdn-repeat",
    "image": image,
    "image_id": image_id,
    "gdn_native_fallback": "0",
    "strict_rates_tok_s": {
        "native-A": a[1]["summary"][metric]["median"],
        "native-B": b[1]["summary"][metric]["median"],
    },
    "exact_repeat": {"exact": exact, "total": len(prompts), "mismatching_prompt_ids": bad},
    "performance_sha256": {
        "native-A": hashlib.sha256((a[0] / "performance.json").read_bytes()).hexdigest(),
        "native-B": hashlib.sha256((b[0] / "performance.json").read_bytes()).hexdigest(),
    },
    "preregistration_sha256": hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest(),
    "quality_attestation_required": passed,
    "mtp_authorized": False,
}
out = parent / f"{campaign}-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
if not passed:
    raise SystemExit(3)
PY
