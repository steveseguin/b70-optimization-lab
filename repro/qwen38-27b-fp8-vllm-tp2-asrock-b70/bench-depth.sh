#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
port="${PORT:-18088}"
base_url="${BASE_URL:-http://127.0.0.1:${port}}"
out_dir="${OUT_DIR:-${PWD}/qwen38-fp8-tp2-depth}"
served_model="${SERVED_MODEL_NAME:-qwen38-fp8}"
fixture="${repo_root}/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
client="${repo_root}/scripts/bench-openai-token-depth-suite.py"

[[ ! -e "${out_dir}" ]] || { printf 'refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
mkdir -p "${out_dir}"
curl -fsS "${base_url}/health" >/dev/null

for depth in 2048 4096 8192 16384 24576 32768; do
  python3 "${client}" --execute --fixture "${fixture}" --depth "${depth}" \
    --context-capacity 33024 --base-url "${base_url}" --model "${served_model}" \
    --response-adapter vllm --timeout 1800 \
    --out "${out_dir}/depth-${depth}.json" >"${out_dir}/depth-${depth}.stdout.json"
done

python3 -B - "${out_dir}" >"${out_dir}/summary.json" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
depths = [2048, 4096, 8192, 16384, 24576, 32768]
points = []
for depth in depths:
    row = json.loads((root / f"depth-{depth}.json").read_text())
    ttft = row["metric_window"]["time_to_first_token_s"]
    points.append({
        "active_context_tokens": depth,
        "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_ms": ttft * 1000,
        "effective_prompt_throughput_proxy_tok_s": depth / ttft,
        "cached_tokens_zero": row["gate"]["checks"]["cached_tokens_zero"],
        "status": row["status"],
    })
passed = all(point["status"] == "passed" and point["cached_tokens_zero"] for point in points)
json.dump({
    "classification": "qualified-exact-depth" if passed else "failed-closed",
    "points": points,
    "proxy_boundary": "prompt tokens divided by HTTP TTFT; includes scheduling and first-token work",
}, sys.stdout, indent=2, sort_keys=True)
print()
if not passed:
    raise SystemExit(2)
PY

printf 'PASS: %s\n' "${out_dir}"
