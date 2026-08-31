#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
attempt_runner=${script_dir}/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh
campaign=${CAMPAIGN:?set CAMPAIGN}
prereg=${PREREG:?set PREREG}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
cache_parent=${CACHE_DIR:-/mnt/fast-ai/vllm-cache}
model=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
image_id=${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID}
xpu_sha=${EXPECTED_XPU_EXTENSION_SHA256:?set EXPECTED_XPU_EXTENSION_SHA256}
gdn_sha=${EXPECTED_GDN_LIBRARY_SHA256:?set EXPECTED_GDN_LIBRARY_SHA256}
gpu_ids=${GPU_IDS:-0,1}
min_host_memory_gib=${MIN_HOST_MEMORY_GIB:-8}
container_memory=${CONTAINER_MEMORY:-12g}
container_memory_swap=${CONTAINER_MEMORY_SWAP:-36g}

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "$prereg" ]] || fail "missing preregistration: $prereg"
[[ -x "$attempt_runner" ]] || fail "missing attempt runner: $attempt_runner"
[[ -d "$model" && ! -L "$model" ]] || fail "model must be a real local directory: $model"
[[ "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be on ext4'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'

git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'

common=(
  IMAGE="$image"
  EXPECTED_IMAGE_ID="$image_id"
  EXPECTED_XPU_EXTENSION_SHA256="$xpu_sha"
  EXPECTED_GDN_LIBRARY_SHA256="$gdn_sha"
  MODEL_DIR="$model"
  GPU_IDS="$gpu_ids"
  MIN_HOST_MEMORY_GIB="$min_host_memory_gib"
  CONTAINER_MEMORY="$container_memory"
  CONTAINER_MEMORY_SWAP="$container_memory_swap"
)

run_arm() {
  local mode=$1 label=$2 port=$3
  local root=${out_parent}/${campaign}-${label}
  local cache=${cache_parent}/${campaign}-${label}
  env "${common[@]}" EXECUTION_MODE="$mode" ATTEMPT="$label" \
    OUT_DIR="$root" VLLM_CACHE_DIR="$cache" PORT="$port" "$attempt_runner"
}

run_arm eager eager-oracle 18161
run_arm compiled compiled-A 18162
python3 - \
  "${out_parent}/${campaign}-eager-oracle/performance.json" \
  "${out_parent}/${campaign}-compiled-A/performance.json" <<'PY'
import json, sys

def rows(path):
    value = json.load(open(path))
    return {row["prompt_id"]: row["token_ids"] for row in value["rows"]}

eager, candidate = map(rows, sys.argv[1:])
if candidate != eager:
    exact = sum(candidate.get(prompt) == ids for prompt, ids in eager.items())
    raise SystemExit(f"compiled A failed eager oracle: {exact}/{len(eager)} exact")
print(f"compiled_A_exact_vs_eager={len(eager)}/{len(eager)}")
PY
run_arm compiled compiled-B 18163

python3 - "$out_parent" "$campaign" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import statistics
import sys

parent, campaign, prereg, image, image_id = sys.argv[1:]
parent = pathlib.Path(parent)

def load(label):
    root = parent / f"{campaign}-{label}"
    perf = json.loads((root / "performance.json").read_text())
    qual = json.loads((root / "qualification.json").read_text())
    rows = {row["prompt_id"]: row["token_ids"] for row in perf["rows"]}
    return root, perf, qual, rows

arms = {label: load(label) for label in ("eager-oracle", "compiled-A", "compiled-B")}
eager = arms["eager-oracle"][3]
exact = {
    label: {
        "exact_count": sum(ids == eager[prompt] for prompt, ids in rows.items()),
        "total": len(eager),
    }
    for label, (_, _, _, rows) in arms.items()
}
rates = {
    label: value[2]["strict_metric_tok_s"]
    for label, value in arms.items()
}
passed = (
    all(value[2]["status"] == "passed" for value in arms.values())
    and set(eager) == set(arms["compiled-A"][3]) == set(arms["compiled-B"][3])
    and exact["compiled-A"]["exact_count"] == len(eager)
    and exact["compiled-B"]["exact_count"] == len(eager)
    and arms["compiled-A"][3] == arms["compiled-B"][3]
)
result = {
    "schema": "neural.download.qwen38-autoround-deterministic-mtp0-campaign.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": campaign,
    "classification": "qualified-deterministic-parent" if passed else "failed-closed",
    "image": image,
    "image_id": image_id,
    "preregistration": prereg,
    "preregistration_sha256": hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest(),
    "strict_rates_tok_s": rates,
    "compiled_median_tok_s": statistics.median([rates["compiled-A"], rates["compiled-B"]]),
    "exact_vs_eager": exact,
    "all_correctness_gates_passed": passed,
    "mtp1_authorized": passed,
    "reporting_boundary": "MTP0 deterministic-parent qualification only; no MTP or aggregate claim."
}
out = parent / f"{campaign}-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
if not passed:
    raise SystemExit(3)
PY
