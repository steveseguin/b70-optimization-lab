#!/usr/bin/env bash
set -euo pipefail
set -o noclobber

CAMPAIGN_ID='qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1'
EXPECTED_ACK="RUN $CAMPAIGN_ID"
REPO='/home/steve/llm-optimizations'
MANIFEST="$REPO/experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"
VALIDATOR="$REPO/experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py"
SERVER='/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-server'
MODEL='/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_K_M.gguf'
FIXTURE="$REPO/data/qwen27-exact-depth/qwen36-6a9e13bd-exact-depth-v1.json"
DEPTH_CLIENT="$REPO/scripts/bench-openai-token-depth-suite.py"
QUALITY_CLIENT="$REPO/scripts/qwen36-text-quality-suite.py"
TOKENIZER='/mnt/fast-ai/llm-cache/hf/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9'
RUN_ROOT='/mnt/fast-ai/bench-results/qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1'
RENDER='/dev/dri/by-path/pci-0000:23:00.0-render'
PORT=19432
MODEL_ALIAS='qwen36-q4km-f16-tp1'
ACK=''

while (($#)); do
  case "$1" in
    --ack) ACK="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$ACK" == "$EXPECTED_ACK" ]] || { echo "exact --ack required" >&2; exit 2; }

sha_check() {
  local expected="$1" path="$2"
  [[ -f "$path" ]] || { echo "missing: $path" >&2; exit 2; }
  [[ "$(sha256sum "$path" | awk '{print $1}')" == "$expected" ]] || {
    echo "checksum mismatch: $path" >&2; exit 2;
  }
}

sha_check 2421d1b28fe96a552759fdcb68ee3f80936b7a2b01852376c0003debd99e9889 "$SERVER"
sha_check a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f "$MODEL"
sha_check 85b1050c88b4c1e6cb9c4ce7f1580284cd2aa68243dad0d0dff16460decbe5ac "$FIXTURE"
sha_check 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 "$DEPTH_CLIENT"
sha_check 6e91e669a6d1ec005b32b141ea7ed859cae64657e99fc262506235eb0cfaa365 "$QUALITY_CLIENT"
[[ -d "$TOKENIZER" ]] || { echo "missing tokenizer: $TOKENIZER" >&2; exit 2; }

cd "$REPO"
[[ -z "$(git status --porcelain)" ]] || { echo 'main must be clean' >&2; exit 2; }
git fetch origin main --quiet
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || {
  echo 'HEAD must equal origin/main' >&2; exit 2;
}

mkdir -p /run/user/1000/qwen36-b70-gpu-leases
exec 9>>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 9 || { echo 'canonical GPU lock held' >&2; exit 3; }
exec 8>>/tmp/b70-benchmark.lock
flock -n 8 || { echo 'benchmark lock held' >&2; exit 3; }
exec 7>>/tmp/b70-gpu0.lock
flock -n 7 || { echo 'GPU0 lock held' >&2; exit 3; }
exec 6>>/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock
flock -n 6 || { echo 'Qwen GPU0 lease held' >&2; exit 3; }

server_pid=''
terminal_written=0
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ -d "$RUN_ROOT" && ! -e "$RUN_ROOT/terminal-receipt.json" ]]; then
    python3 - "$RUN_ROOT/terminal-receipt.json" "$CAMPAIGN_ID" "$rc" <<'PY' || true
import datetime as dt, json, pathlib, sys
p=pathlib.Path(sys.argv[1])
with p.open('x') as f:
    json.dump({'schema':'neural.download.qwen36-llama-mtp1-parent-sentinel-terminal.v1','campaign_id':sys.argv[2],'created_at_utc':dt.datetime.now(dt.UTC).isoformat(),'status':'failed-preserve-do-not-expand','exit_code':int(sys.argv[3])},f,indent=2,sort_keys=True); f.write('\n')
PY
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

active_model_processes() {
  python3 - <<'PY'
from pathlib import Path

exact_comms = {"llama-bench", "llama-batched-bench", "llama-server"}
markers = (
    "llama-bench",
    "llama-batched-bench",
    "llama-server",
    "vllm.entrypoints",
    "vllm serve",
    "VLLM::EngineCore",
)
matches = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        comm = (entry / "comm").read_text(encoding="utf-8").strip()
        cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            errors="replace"
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue
    if comm in exact_comms or any(marker in cmdline for marker in markers):
        matches.append(f"{entry.name}:{comm}")
print("\n".join(matches))
PY
}

require_idle() {
  local busy
  busy="$(active_model_processes)"
  [[ -z "$busy" ]] || { echo "model process active: $busy" >&2; exit 3; }
  if command -v docker >/dev/null && [[ -n "$(docker ps -q 2>/dev/null)" ]]; then
    echo 'container active' >&2; exit 3
  fi
  [[ -e "$RENDER" ]] || { echo "missing render node: $RENDER" >&2; exit 3; }
  [[ -z "$(fuser "$RENDER" 2>/dev/null || true)" ]] || { echo 'GPU0 busy' >&2; exit 3; }
  ! ss -ltnH "sport = :$PORT" | grep -q . || { echo "port $PORT busy" >&2; exit 3; }
}

require_idle
[[ ! -e "$RUN_ROOT" ]] || { echo "create-only root exists: $RUN_ROOT" >&2; exit 3; }
[[ "$(findmnt -no FSTYPE --target "$(dirname "$RUN_ROOT")")" == ext4 ]] || {
  echo 'run root parent must be ext4' >&2; exit 3;
}
mkdir "$RUN_ROOT"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
version="$($SERVER --version 2>&1)"
grep -Fq 'version: 9976 (e3546c794)' <<<"$version" || { echo 'server version drift' >&2; exit 3; }
help_text="$($SERVER --help 2>&1)"
grep -Fq 'draft-mtp' <<<"$help_text" || { echo 'server lacks draft-mtp' >&2; exit 3; }

{
  echo "campaign_id=$CAMPAIGN_ID"
  echo "git_head=$(git rev-parse HEAD)"
  echo "server_sha256=$(sha256sum "$SERVER" | awk '{print $1}')"
  echo "model_sha256=$(sha256sum "$MODEL" | awk '{print $1}')"
  echo "fixture_sha256=$(sha256sum "$FIXTURE" | awk '{print $1}')"
  echo "$version"
  ldd "$SERVER"
} > "$RUN_ROOT/identity.txt"

common_args=(
  -m "$MODEL" --alias "$MODEL_ALIAS" --host 127.0.0.1 --port "$PORT"
  -dev SYCL0 -ngl 99 -sm layer -c 12288 -np 1 -b 2048 -ub 512 -t 16
  --poll 50 -fa on -ctk f16 -ctv f16 --reasoning off --ctx-checkpoints 0
  --cache-ram 0 --jinja --no-webui
)

start_server() {
  local arm="$1"; shift
  mkdir "$RUN_ROOT/$arm"
  env \
    ONEAPI_DEVICE_SELECTOR='level_zero:*' ZE_AFFINITY_MASK=0 ZES_ENABLE_SYSMAN=1 \
    UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    GGML_SYCL_ENABLE_GRAPH=0 GGML_SYCL_GRAPH_CACHE_SIZE=0 \
    GGML_SYCL_ENABLE_DNN=1 GGML_SYCL_ENABLE_OPT=1 GGML_SYCL_ENABLE_VMM=1 \
    GGML_SYCL_FUSE_MMVQ_ADD=0 GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8=0 \
    GGML_SYCL_FUSE_SWIGLU_Q8=0 GGML_SYCL_FUSE_SSM_CONV_SILU=0 \
    GGML_SYCL_FUSE_SSM_CONV_CACHE=0 GGML_SYCL_FUSE_SSM_CONV_QK_NORM=0 \
    GGML_SYCL_FUSE_GDN_CACHE=0 GGML_SYCL_FUSE_GDN_RAW_GATES=0 \
    GGML_SYCL_FUSE_GDN_EPILOGUE=0 LLAMA_MTP_DEVICE_UNROLL=0 \
    "$SERVER" "${common_args[@]}" "$@" > "$RUN_ROOT/$arm/server.log" 2>&1 &
  server_pid=$!
  local deadline=$((SECONDS + 300))
  until curl -fsS "http://127.0.0.1:$PORT/v1/models" > "$RUN_ROOT/$arm/models.json"; do
    kill -0 "$server_pid" 2>/dev/null || { echo "$arm server exited" >&2; exit 4; }
    ((SECONDS < deadline)) || { echo "$arm readiness timeout" >&2; exit 4; }
    sleep 2
  done
}

stop_server() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  server_pid=''
  [[ -z "$(fuser "$RENDER" 2>/dev/null || true)" ]] || { echo 'GPU0 remained busy' >&2; exit 4; }
}

run_depth() {
  local arm="$1"
  python3 -B "$DEPTH_CLIENT" --execute --fixture "$FIXTURE" --depth 8192 \
    --case-id depth-8192 --context-capacity 12288 \
    --base-url "http://127.0.0.1:$PORT" --model "$MODEL_ALIAS" \
    --response-adapter llama-server --timeout 3600 \
    --out "$RUN_ROOT/$arm/exact-depth.json" > "$RUN_ROOT/$arm/exact-depth.stdout.json"
}

require_idle
start_server control-mtp0 --spec-type none
run_depth control-mtp0
stop_server

require_idle
start_server candidate-mtp1 \
  --spec-type draft-mtp --spec-draft-n-max 1 --spec-draft-n-min 1 \
  --spec-draft-p-min 0 --spec-draft-device SYCL0 --spec-draft-ngl all \
  --spec-draft-type-k f16 --spec-draft-type-v f16
run_depth candidate-mtp1
python3 -B "$QUALITY_CLIENT" --base-url "http://127.0.0.1:$PORT" \
  --model "$MODEL_ALIAS" --tokenizer "$TOKENIZER" --timeout 3600 \
  --repeat-runs 2 --long-context-tokens 8192 \
  --request-id-prefix qwen36-q4km-mtp1-parent-r1 \
  --output-json "$RUN_ROOT/candidate-mtp1/quality.json" \
  > "$RUN_ROOT/candidate-mtp1/quality.stdout.json"
stop_server

[[ -z "$(fuser "$RENDER" 2>/dev/null || true)" ]] || { echo 'GPU0 busy at postflight' >&2; exit 4; }
python3 -B "$VALIDATOR" --root "$RUN_ROOT" --manifest "$MANIFEST" \
  --output "$RUN_ROOT/terminal-receipt.json" > "$RUN_ROOT/validator.stdout.json"
terminal_written=1
echo "$RUN_ROOT/terminal-receipt.json"
