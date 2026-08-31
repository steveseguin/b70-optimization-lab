#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
attempt_runner=${script_dir}/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh
campaign=qwen38-autoround-allreduce-sync-tp2-20260830-r4
out_parent=/mnt/fast-ai/bench-results
cache_parent=/mnt/fast-ai/vllm-cache
image=neural-download/vllm-openai-xpu:qwen38-autoround-allreduce-sync-diagnostic-r4
image_id=sha256:aa212832d5ba6d88d2fa47d1ce9b08ce3862e90bbd4aa57156d6eaafef14f1d2
communicator_sha=c9a356a5a11006206ae83da9c09fd6cee86e9cd6f65e8d8d877bfe08d0762373
prereg=${repo}/experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-autoround-allreduce-sync-tp2-r4-prereg.md

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "$prereg" && -x "$attempt_runner" ]] || fail 'missing preregistration or runner'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
[[ "$(docker image inspect "$image" --format '{{index .Config.Labels "neural.download.xpu-communicator.sha256"}}')" == "$communicator_sha" ]] || fail 'communicator label mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

run_arm() {
  local label=$1 port=$2
  env EXECUTION_MODE=compiled ATTEMPT="$label" IMAGE="$image" \
    EXPECTED_IMAGE_ID="$image_id" \
    EXPECTED_XPU_EXTENSION_SHA256=c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620 \
    EXPECTED_GDN_LIBRARY_SHA256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355 \
    EXPECTED_XPU_COMMUNICATOR_SHA256="$communicator_sha" \
    MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround \
    GPU_IDS=0,1 MIN_HOST_MEMORY_GIB=8 CONTAINER_MEMORY=12g CONTAINER_MEMORY_SWAP=36g \
    OUT_DIR="${out_parent}/${campaign}-${label}" \
    VLLM_CACHE_DIR="${cache_parent}/${campaign}-${label}" PORT="$port" \
    "$attempt_runner"
}

run_arm sync-A 18166
run_arm sync-B 18167

python3 - "$out_parent" "$campaign" "$prereg" "$image" "$image_id" <<'PY'
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

a = load("sync-A")
b = load("sync-B")
prompts = sorted(set(a[3]) | set(b[3]))
mismatches = [prompt for prompt in prompts if a[3].get(prompt) != b[3].get(prompt)]
exact = len(prompts) - len(mismatches)
metric = "class_balanced_tok_s_1_100_intervals_after_ttft"
passed = a[2]["status"] == b[2]["status"] == "passed" and exact == 12
result = {
    "schema": "neural.download.qwen38-autoround-allreduce-sync-diagnostic.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": campaign,
    "classification": "positive-collective-boundary-diagnostic" if passed else "negative-collective-boundary-diagnostic",
    "image": image,
    "image_id": image_id,
    "strict_rates_tok_s": {
        "sync-A": a[1]["summary"][metric]["median"],
        "sync-B": b[1]["summary"][metric]["median"],
    },
    "exact_repeat": {"exact": exact, "total": len(prompts), "mismatching_prompt_ids": mismatches},
    "performance_sha256": {
        "sync-A": hashlib.sha256((a[0] / "performance.json").read_bytes()).hexdigest(),
        "sync-B": hashlib.sha256((b[0] / "performance.json").read_bytes()).hexdigest(),
    },
    "preregistration_sha256": hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest(),
    "reporting_boundary": "Whole-device synchronization causal diagnostic only; speed is non-promotable and MTP remains unauthorized.",
}
out = parent / f"{campaign}-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
if not passed:
    raise SystemExit(3)
PY
