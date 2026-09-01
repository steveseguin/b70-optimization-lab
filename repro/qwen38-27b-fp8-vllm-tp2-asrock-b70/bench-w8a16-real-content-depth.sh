#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new output directory}
arm=${ARM:?set ARM to mtp0 or mtp1}
base_url=${BASE_URL:-http://127.0.0.1:18124}
served_model=${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-${arm}-depth}
oracle_dir=${ORACLE_DIR:-}
fixture=${FIXTURE:-${repo_root}/data/qwen27-exact-depth/qwen38-bce40ca-mixed-content-depth-v1.json}
client=${repo_root}/scripts/bench-openai-token-depth-suite.py
canary_client=${repo_root}/scripts/neural-download-canaries.py
context_capacity=33024

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${arm}" == mtp0 || "${arm}" == mtp1 ]] || fail 'ARM must be mtp0 or mtp1'
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
for required in "${fixture}" "${client}" "${canary_client}"; do
  [[ -f "${required}" ]] || fail "missing tracked input: ${required}"
done
if [[ "${arm}" == mtp1 ]]; then
  [[ -n "${oracle_dir}" && -f "${oracle_dir}/summary.json" ]] || \
    fail 'MTP1 requires ORACLE_DIR pointing to a completed MTP0 arm'
fi
curl -fsS "${base_url}/health" >/dev/null || fail "server is not healthy: ${base_url}"
mkdir -p "${out_dir}"

sha256sum "${fixture}" "${client}" "${canary_client}" >"${out_dir}/input-sha256sums.txt"
curl -fsS "${base_url}/v1/models" >"${out_dir}/models.json"
curl -fsS "${base_url}/metrics" >"${out_dir}/metrics-before.txt" || true
python3 "${canary_client}" --base-url "${base_url}" --model "${served_model}" \
  --out "${out_dir}/canaries-before.json" >"${out_dir}/canaries-before.stdout"

classes=(technical-prose python-code structured-docs)
depths=(2048 4096 8192 16384 24576 32768)
for depth in "${depths[@]}"; do
  for content_class in "${classes[@]}"; do
    case_id=${content_class}-depth-${depth}
    python3 "${client}" --execute --fixture "${fixture}" --depth "${depth}" \
      --case-id "${case_id}" --context-capacity "${context_capacity}" \
      --base-url "${base_url}" --model "${served_model}" \
      --response-adapter vllm --timeout 1800 \
      --out "${out_dir}/${case_id}.json" \
      >"${out_dir}/${case_id}.stdout.json"
  done
done

python3 "${canary_client}" --base-url "${base_url}" --model "${served_model}" \
  --out "${out_dir}/canaries-after.json" >"${out_dir}/canaries-after.stdout"
curl -fsS "${base_url}/metrics" >"${out_dir}/metrics-after.txt" || true

python3 - "${out_dir}" "${arm}" "${oracle_dir}" "${fixture}" <<'PY'
import hashlib
import json
import math
import pathlib
import statistics
import sys

root = pathlib.Path(sys.argv[1])
arm = sys.argv[2]
oracle_dir = pathlib.Path(sys.argv[3]) if sys.argv[3] else None
fixture = pathlib.Path(sys.argv[4])
depths = (2048, 4096, 8192, 16384, 24576, 32768)
classes = ("technical-prose", "python-code", "structured-docs")
oracle = json.loads((oracle_dir / "summary.json").read_text()) if oracle_dir else None
expected = {row["case_id"]: row for row in oracle["cases"]} if oracle else {}
cases = []
for depth in depths:
    for content_class in classes:
        case_id = f"{content_class}-depth-{depth}"
        path = root / f"{case_id}.json"
        row = json.loads(path.read_text())
        output_hash = row["response"]["output_token_ids_sha256"]
        cases.append({
            "case_id": case_id,
            "class": content_class,
            "active_context_tokens": depth,
            "receipt": path.name,
            "receipt_status": row["status"],
            "cache_zero": row["gate"]["checks"]["cached_tokens_zero"],
            "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"],
            "ttft_ms": row["metric_window"]["time_to_first_token_s"] * 1000,
            "output_token_ids_sha256": output_hash,
            "output_token_ids": row["response"]["token_ids"],
            "target_oracle_exact": None if oracle is None else (
                row["response"]["token_ids"] == expected[case_id]["output_token_ids"]
            ),
        })

before = json.loads((root / "canaries-before.json").read_text())
after = json.loads((root / "canaries-after.json").read_text())
points = []
for depth in depths:
    selected = [row for row in cases if row["active_context_tokens"] == depth]
    points.append({
        "active_context_tokens": depth,
        "classes": list(classes),
        "samples": len(selected),
        "median_decode_tok_s": statistics.median(row["decode_tok_s"] for row in selected),
        "median_ttft_ms": statistics.median(row["ttft_ms"] for row in selected),
        "all_request_gates_passed": len(selected) == 3 and all(
            row["receipt_status"] == "passed" and row["cache_zero"] for row in selected
        ),
        "all_target_oracle_exact": None if oracle is None else (
            len(selected) == 3 and all(row["target_oracle_exact"] for row in selected)
        ),
    })

base_pass = (
    len(cases) == 18
    and all(
        row["receipt_status"] == "passed"
        and row["cache_zero"]
        and math.isfinite(row["decode_tok_s"])
        and row["decode_tok_s"] > 0
        for row in cases
    )
    and before["pass_all"]
    and after["pass_all"]
)
exact_pass = arm == "mtp0" or all(row["target_oracle_exact"] for row in cases)
passed = base_pass and exact_pass
result = {
    "schema": "neural.download.qwen38-fp8-tp2-real-content-depth-arm.v1",
    "arm": arm,
    "status": "passed" if passed else "failed-closed",
    "classification": (
        "Grade B three-class unrepeated real-content exact-depth HTTP evidence"
        if passed else "invalid-or-partial"
    ),
    "fixture": {
        "path": str(fixture),
        "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "source_repetition": False,
        "natural_task_or_retrieval_prompt": False,
    },
    "identity": {
        "model": "Qwen3.8-27B official FP8",
        "cards": 2,
        "tensor_parallel": 2,
        "mtp_depth": 0 if arm == "mtp0" else 1,
        "context_capacity": 33024,
        "parallel_slots": 1,
        "prompt_cache": False,
        "kv_dtype": "f16",
    },
    "cases": cases,
    "points": points,
    "canaries": {"before": before["pass_all"], "after": after["pass_all"]},
    "oracle": None if oracle_dir is None else {"path": str(oracle_dir / "summary.json")},
    "publication_boundary": (
        "Per-depth medians across technical prose, Python code, and structured "
        "documentation. Every point is directly measured; no interpolation or "
        "extrapolation. This is representative continuation shape evidence, not "
        "a natural retrieval/task accuracy suite. MTP1 must exactly match every "
        "complete MTP0 output-token array."
    ),
}
(root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": result["status"], "arm": arm, "points": points}, indent=2))
if not passed:
    raise SystemExit(3)
PY

sha256sum "${out_dir}"/*.json >"${out_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${out_dir}"
