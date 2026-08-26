#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
campaign=qwen38-official-fp8-tp1-fit-depth-20260826-r1
ack="RUN ${campaign}"
prereg="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r1-prereg.json"
verifier="${repo_root}/experiments/qwen38-27b-b70/scripts/verify-20260826-qwen38-official-fp8-tp1-fit-depth-r1.py"
model_dir=/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7
image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'
fixture="${repo_root}/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
client="${repo_root}/scripts/bench-openai-token-depth-suite.py"
out_root=/mnt/fast-ai/bench-results/${campaign}
cache_root=/mnt/fast-ai/vllm-cache/qwen38-official-fp8-f01e-tp1-fit-depth-r1
port=19453

fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 2; }

if [[ "${1:-}" != --execute ]]; then
  exec python3 -B "${verifier}"
fi
shift
[[ "${1:-}" == --ack && "${2:-}" == "${ack}" && $# == 2 ]] || fail "exact arguments required: --execute --ack '${ack}'"

[[ -f "${prereg}" && -f "${verifier}" && -f "${fixture}" && -f "${client}" ]] || fail 'frozen packet input missing'
[[ ! -e "${out_root}" ]] || fail "create-only output exists: ${out_root}"
[[ "$(findmnt -no FSTYPE --target /mnt/fast-ai)" == ext4 ]] || fail '/mnt/fast-ai must be ext4'
for inherited in GGML_SYCL_ENABLE_GRAPH VLLM_XPU_ENABLE_XPU_GRAPH ONEAPI_DEVICE_SELECTOR ZE_AFFINITY_MASK SYCL_DEVICE_FILTER LD_PRELOAD; do
  [[ -z "${!inherited:-}" ]] || fail "unexpected inherited runtime variable: ${inherited}"
done

git -C "${repo_root}" fetch origin main --quiet
[[ "$(git -C "${repo_root}" rev-parse HEAD)" == "$(git -C "${repo_root}" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "${repo_root}" status --porcelain)" ]] || fail 'repository must be clean'
docker image inspect "${image}" >/dev/null 2>&1 || fail 'exact pinned image is not local; this packet will not pull it'

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir "${out_root}"
mkdir -p "${cache_root}"
docker image inspect "${image}" >"${out_root}/image-inspect.json"
sha256sum "${prereg}" "${verifier}" "${fixture}" "${client}" >"${out_root}/input-sha256sums.txt"
if ! python3 -B "${verifier}" --verify >"${out_root}/model-verification.json" 2>"${out_root}/model-verification.stderr.log"; then
  python3 -B - "${out_root}" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);json.dump({"schema":"neural.download.qwen38-official-fp8-tp1-fit-depth-terminal.v1","campaign_id":"qwen38-official-fp8-tp1-fit-depth-20260826-r1","status":"blocked-model-verification-do-not-launch","authority":{"measured_cells":0,"unsupported_cells":0}},(root/"terminal-receipt.json").open("x"),indent=2,sort_keys=True)
PY
  fail 'strict complete-model verification failed; no GPU service launched'
fi

cleanup_container(){
  local container=$1 arm_root=$2
  set +e
  docker logs "${container}" >"${arm_root}/server.log" 2>&1
  docker stop -t 20 "${container}" >/dev/null 2>&1
  docker rm -f "${container}" >/dev/null 2>&1
  set -e
  active_container=''
}

active_container=''
emergency_cleanup(){
  if [[ -n "${active_container}" ]]; then
    docker stop -t 5 "${active_container}" >/dev/null 2>&1 || true
    docker rm -f "${active_container}" >/dev/null 2>&1 || true
  fi
}
trap emergency_cleanup EXIT INT TERM

selected=''
measurement_failure=0
for spec in '8192:8448:8192,4096,2048' '4096:4352:4096,2048' '2048:2304:2048'; do
  IFS=: read -r depth capacity cells <<<"${spec}"
  arm=fit-$((depth/1024))k
  arm_root="${out_root}/${arm}"
  arm_cache="${cache_root}/${arm}"
  container="qwen38-official-fp8-tp1-fit-r1-${depth}"
  mkdir "${arm_root}"
  mkdir -p "${arm_cache}"
  docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" && fail "campaign container already exists: ${container}"
  cmd=(docker run -d --name "${container}" --memory 12g --memory-swap 16g
    --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE
    --security-opt label=disable --ipc=host --shm-size=8g
    -p "127.0.0.1:${port}:8000"
    -v "${model_dir}:/model:ro" -v "${arm_cache}:/root/.cache/vllm"
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0
    -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn
    -e VLLM_XPU_ENABLE_XPU_GRAPH=0 -e PYTORCH_ALLOC_CONF=expandable_segments:True
    --entrypoint bash "${image}" -lc
    "exec vllm serve /model --served-model-name qwen38-official-fp8-tp1 --host 0.0.0.0 --port 8000 --tensor-parallel-size 1 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.98 --max-model-len ${capacity} --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 2048 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --enforce-eager")
  printf '%q ' "${cmd[@]}" >"${arm_root}/server-command.txt";printf '\n' >>"${arm_root}/server-command.txt"
  active_container="${container}"
  if ! "${cmd[@]}" >"${arm_root}/container-id.txt"; then
    printf '{"status":"startup-command-failed","explicit_fit_failure":false}\n' >"${arm_root}/arm-result.json"
    cleanup_container "${container}" "${arm_root}"
    continue
  fi
  healthy=0
  for _ in $(seq 1 600); do
    if curl -fsS "http://127.0.0.1:${port}/health" >"${arm_root}/health.json" 2>/dev/null; then healthy=1;break;fi
    docker ps --format '{{.Names}}' | grep -Fxq "${container}" || break
    sleep 1
  done
  docker logs "${container}" >"${arm_root}/server.log" 2>&1 || true
  if (( healthy == 0 )); then
    explicit=false
    if grep -Eqi 'out of memory|not enough memory|cannot allocate memory|no available memory for the cache blocks|free memory on device.*less than desired|failed to allocate' "${arm_root}/server.log"; then explicit=true;fi
    python3 -B - "${arm_root}" "${explicit}" "${depth}" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);json.dump({"status":"startup-failed-preserve","active_context_tokens":int(sys.argv[3]),"explicit_fit_failure":sys.argv[2]=="true"},(root/"arm-result.json").open("x"),indent=2,sort_keys=True)
PY
    cleanup_container "${container}" "${arm_root}"
    continue
  fi
  if ! curl -fsS "http://127.0.0.1:${port}/v1/models" >"${arm_root}/models.json"; then
    cleanup_container "${container}" "${arm_root}"
    printf '{"status":"readiness-model-list-failed-invalid-preserve","explicit_fit_failure":false}\n' >"${arm_root}/arm-result.json"
    measurement_failure=1
    break
  fi
  IFS=, read -ra measure_depths <<<"${cells}"
  receipt_ok=1
  for measured in "${measure_depths[@]}"; do
    if ! python3 -B "${client}" --execute --fixture "${fixture}" --depth "${measured}" --context-capacity "${capacity}" --base-url "http://127.0.0.1:${port}" --model qwen38-official-fp8-tp1 --response-adapter vllm --timeout 1800 --out "${arm_root}/depth-${measured}.json" >"${arm_root}/depth-${measured}.stdout.json" 2>"${arm_root}/depth-${measured}.stderr.log"; then receipt_ok=0;break;fi
  done
  cleanup_container "${container}" "${arm_root}"
  if (( receipt_ok == 0 )); then
    printf '{"status":"receipt-failed-invalid-preserve","explicit_fit_failure":false}\n' >"${arm_root}/arm-result.json"
    measurement_failure=1
    break
  fi
  if ! python3 -B - "${arm_root}" "${depth}" "${capacity}" "${cells}" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);depths=[int(x) for x in sys.argv[4].split(',')]
rows=[]
for depth in depths:
    value=json.loads((root/f"depth-{depth}.json").read_text());rows.append({"active_context_tokens":depth,"status":value["status"],"serving_decode_tok_s_99_interval":value["metric_window"]["conventional_99_interval_tok_s"],"cached_tokens":value["response"]["usage"]["prompt_tokens_details"]["cached_tokens"],"output_token_ids_sha256":value["response"]["output_token_ids_sha256"]})
passed=all(row["status"]=="passed" and row["cached_tokens"]==0 and row["serving_decode_tok_s_99_interval"]>0 for row in rows)
json.dump({"status":"completed-awaiting-terminal" if passed else "receipt-failed-invalid-preserve","first_supported_depth":int(sys.argv[2]),"context_capacity_tokens":int(sys.argv[3]),"explicit_fit_failure":False,"cells":rows},(root/"arm-result.json").open("x"),indent=2,sort_keys=True)
if not passed:raise SystemExit(2)
PY
  then
    measurement_failure=1
    break
  fi
  selected="${arm}"
  break
done

python3 -B - "${out_root}" "${selected}" "${measurement_failure}" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);selected=sys.argv[2];measurement_failed=sys.argv[3]=='1'
arms=[]
for name in ('fit-8k','fit-4k','fit-2k'):
    path=root/name/'arm-result.json'
    if path.exists():arms.append({"arm":name,**json.loads(path.read_text())})
if selected:
    winner=next(row for row in arms if row['arm']==selected);cells=winner['cells'];status='completed-valid-bounded-fit-depth';classification='Grade C exact-depth serving cells at the first supported official-FP8 TP1 capacity'
elif measurement_failed:
    cells=[];status='failed-invalid-do-not-publish';classification='service booted but exact serving receipt failed'
else:
    cells=[];last=arms[-1] if arms else {};explicit=last.get('arm')=='fit-2k' and last.get('explicit_fit_failure') is True;status='completed-unsupported-official-fp8-tp1-at-or-above-2k' if explicit else 'failed-inconclusive-no-cells';classification='durable unsupported fit closure under exact tuple' if explicit else 'bounded startup closure without sufficient evidence for unsupported'
value={"schema":"neural.download.qwen38-official-fp8-tp1-fit-depth-terminal.v1","campaign_id":"qwen38-official-fp8-tp1-fit-depth-20260826-r1","status":status,"classification":classification,"arms":arms,"cells":cells,"authority":{"official_fp8_tp1_grade_c_cells":len(cells),"site_publication":bool(cells),"unsupported_closure":status.startswith('completed-unsupported-'),"tp2_or_tp4_cells":0,"speculative_cells":0,"graph_on_cells":0,"headline_or_protected_replacement":False,"localmaxxing_submission":False},"scope":"Exact official FP8 revision, pinned f01e nightly, TP1, MTP0, eager, FP16/auto KV, one slot; no interpolation."}
json.dump(value,(root/'terminal-receipt.json').open('x'),indent=2,sort_keys=True)
print(json.dumps(value,indent=2,sort_keys=True))
PY

if (( measurement_failure == 1 )); then exit 2;fi
printf 'COMPLETE: %s/terminal-receipt.json\n' "${out_root}"
