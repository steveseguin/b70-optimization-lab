#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
port=${PORT:-18139}
attempt=${ATTEMPT:-r1}
campaign=${CAMPAIGN_ID:-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-20260827-r1}
amendment=${AMENDMENT_PATH:-}
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r1-prereg.json
oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-tp1-mtp0-exact-depth-token-oracle.json
fixture=${repo}/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json
launcher=${repo}/repro/qwen38-27b-q4km-mtp2-tp1-b70/run-server.sh
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ -f "${prereg}" && -f "${oracle}" && -f "${fixture}" && -x "${launcher}" ]] || fail 'sealed campaign dependency missing'
[[ -z "${amendment}" || -f "${amendment}" ]] || fail 'AMENDMENT_PATH does not exist'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == 35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545 ]] || fail 'llama-server SHA mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == 0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154 ]] || fail 'SYCL backend SHA mismatch'
[[ "$(sha256sum "${fixture}" | awk '{print $1}')" == ebe507b725af6ec0713de4084d0bf52fbbab48b151511e0019c1bac2c5051bd9 ]] || fail 'fixture SHA mismatch'
[[ "$(sha256sum "${oracle}" | awk '{print $1}')" == 922be29c65b173872a6857205a33bc78d54572f5d6dac8f8100b69ebbac131ff ]] || fail 'oracle SHA mismatch'

git -C "${repo}" fetch origin main --quiet
[[ "$(git -C "${repo}" rev-parse HEAD)" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "${repo}" status --porcelain)" ]] || fail 'campaign requires a clean worktree'
exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${out_dir}"
sha_inputs=("${prereg}" "${oracle}" "${fixture}" "${launcher}" "${server}" "${backend}")
if [[ -n "${amendment}" ]]; then sha_inputs+=("${amendment}"); fi
sha256sum "${sha_inputs[@]}" >"${out_dir}/sha256sums.txt"
TARGET_DIR=${target_dir} DRAFT_DIR=${draft_dir} BUILD_DIR=${build_dir} \
  "${repo}/repro/qwen38-27b-q4km-mtp2-tp1-b70/verify-models.sh" >"${out_dir}/model-verification.stdout"
free -b >"${out_dir}/memory-before.txt"
xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 >"${out_dir}/xpu-before.txt" 2>&1 || true

server_pid=
cleanup() {
  if pgrep -x llama-server >/dev/null; then pkill -TERM -x llama-server 2>/dev/null || true; fi
  if [[ -n "${server_pid:-}" ]]; then wait "${server_pid}" 2>/dev/null || true; fi
  free -b >"${out_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 >"${out_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

TARGET_DIR=${target_dir} DRAFT_DIR=${draft_dir} BUILD_DIR=${build_dir} PORT=${port} \
  CTX_SIZE=33024 PARALLEL_SLOTS=1 "${launcher}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!
for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; then break; fi
  kill -0 "${server_pid}" 2>/dev/null || fail 'server exited before readiness'
  sleep 2
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null || fail 'server readiness timeout'
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-before.txt" || true

for depth in 2048 4096 8192 16384 24576 32768; do
  python3 "${repo}/scripts/bench-openai-token-depth-suite.py" \
    --execute --fixture "${fixture}" --depth "${depth}" --context-capacity 33024 \
    --base-url "http://127.0.0.1:${port}" --model qwen38-q4km-q4mtp-tp1-mtp2-exact-depth \
    --response-adapter llama-server --timeout 1800 \
    --out "${out_dir}/depth-${depth}.json" >"${out_dir}/depth-${depth}.stdout.json"
  python3 - "${out_dir}/depth-${depth}.json" <<'PY'
import json, sys
receipt = json.load(open(sys.argv[1], encoding="utf-8"))
assert receipt["status"] == "passed"
PY
done

python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model qwen38-q4km-q4mtp-tp1-mtp2-exact-depth \
  --out "${out_dir}/canaries.json" >"${out_dir}/canaries.stdout"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt" || true

python3 - "${out_dir}" "${oracle}" "${attempt}" "${campaign}" >"${out_dir}/summary.json" <<'PY'
import json, math, pathlib, sys
root, oracle_path, attempt, campaign = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
oracle = json.loads(oracle_path.read_text())
expected = {row["active_context_tokens"]: row for row in oracle["points"]}
points = []
receipt_paths = [path for path in root.glob("depth-*.json") if not path.name.endswith(".stdout.json")]
for path in sorted(receipt_paths, key=lambda p: int(p.stem.split("-")[1])):
    row = json.loads(path.read_text())
    depth = row["run_identity"]["active_context_tokens"]
    exact = row["response"]["output_token_ids_sha256"] == expected[depth]["output_token_ids_sha256"]
    points.append({"active_context_tokens": depth, "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"], "ttft_ms": row["metric_window"]["time_to_first_token_s"] * 1000, "cached_tokens_zero": row["gate"]["checks"]["cached_tokens_zero"], "target_oracle_exact": exact, "output_token_ids_sha256": row["response"]["output_token_ids_sha256"]})
canaries = json.loads((root / "canaries.json").read_text())
metrics = (root / "metrics-after.txt").read_text(errors="replace")
def metric(name):
    for line in metrics.splitlines():
        if line.startswith(name + " "):
            return float(line.split()[-1])
    return None
drafted = metric("llamacpp:spec_decode_num_draft_tokens_total")
accepted = metric("llamacpp:spec_decode_num_accepted_tokens_total")
passed = len(points) == 6 and all(p["cached_tokens_zero"] and p["target_oracle_exact"] and math.isfinite(p["decode_tok_s"]) for p in points) and canaries["pass_all"] and drafted is not None and accepted is not None and drafted > 0 and accepted > 0
out = {"schema":"neural.download.qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-result.v1","campaign_id":campaign,"attempt":attempt,"status":"passed" if passed else "failed-closed","classification":"Grade C exact active-context/TTFT curve with MTP0 target-output parity" if passed else "invalid","points":points,"canaries_passed":canaries["pass_all"],"draft_counters":{"drafted":drafted,"accepted":accepted,"acceptance_rate":accepted/drafted if drafted else None},"publication_boundary":"Synthetic repeated-token shape fixture, not natural prose; no interpolation, extrapolation, or single-user headline authority."}
json.dump(out, sys.stdout, indent=2, sort_keys=True); print()
if not passed: raise SystemExit(3)
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'PASS: %s\n' "${out_dir}"
