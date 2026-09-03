#!/usr/bin/env bash
set -euo pipefail

# TP1 (single B70) benchmark for Qwen3.8-27B AutoRound INT4 on the vLLM XPU
# NIGHTLY docker image (0.28-dev line, pinned tag below, pulled 2026-08-22).
# One config per invocation. Fixed realistic suite (25 prompts), conventional
# decode rate = median tokens 1-100 after TTFT, cache-zero (prefix caching
# OFF; harness gates cached_tokens=0 every row). Diagnostic benchmark, not a
# sealed record.
#
# Usage: run-20260822-qwen38-tp1-nightly-docker-bench.sh MTP KV MAXLEN GPUS PORT OUT_DIR SUITE
#   MTP: 0 (off) | 1 | 2 | 3      KV: f16 | fp8_e5m2 | fp8_e4m3
#   GPUS: comma list, e.g. "0" (TP1) | "2,3" (TP2) | "1,2,3" (TP3) | "0,1,2,3" (TP4);
#         tensor-parallel size = number of listed devices
#   SUITE: path to a validation-suite.json
# Env:
#   SUDO_PASS_FILE  if set, docker runs via `sudo -S` reading this file
#                   (never echoed); unset = plain `docker` (docker group).
#   EXTRA_VLLM_ARGS optional extra server args (word-split), e.g. --enforce-eager

IMAGE=vllm/vllm-openai-xpu:nightly-e9d1398d9edfd90fcc1cf783805240e3effec013

mtp=${1:?}; kv=${2:?}; maxlen=${3:?}; gpu=${4:?}; port=${5:?}; out=${6:?}; suite=${7:?}
tp=$(( $(tr -dc ',' <<< "$gpu" | wc -c) + 1 ))
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
# Originating-lab layout; override for another host.
models_root="${QWEN38_MODELS_ROOT:-/mnt/usb-models}"
model="${QWEN38_TP1_MODEL:-$models_root/llm-models/qwen3.8-27b-int4-autoround-devan}"
venv="${VENV:-$HOME/.venvs/vllm-xpu}"
cache_root="${QWEN38_TP1_CACHE_ROOT:-$models_root/llm-runtime/vllm-cache/qwen38-tp1-nightly-20260822}"
[[ -d "$model" ]] || { echo "set QWEN38_TP1_MODEL to the AutoRound INT4 model directory (missing: $model)" >&2; exit 2; }
[[ -x "$venv/bin/python" ]] || { echo "set VENV to a vLLM XPU virtualenv (missing: $venv/bin/python)" >&2; exit 2; }
alias=qwen38-tp1
name="qwen38-tp1-nightly-$port"

dockerc() {
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' docker "$@" < "$SUDO_PASS_FILE"
  else
    docker "$@"
  fi
}

mkdir -p "$out"
[[ -f "$suite" ]] || { echo "missing suite: $suite" >&2; exit 1; }
if dockerc ps --format '{{.Names}}' | grep -qx "$name"; then
  echo "container $name already running" >&2; exit 1
fi
pgrep -af 'EngineCore|vllm serve' | grep -v pgrep >/dev/null && { echo 'a host vLLM server is already running' >&2; exit 1; }

cp -f "$suite" "$out/validation-suite.json"
dockerc image inspect --format '{{.Id}} {{join .RepoDigests ","}}' "$IMAGE" > "$out/image-identity.txt"

# image entrypoint is `vllm serve`, so args begin with the model path
args=( "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
  --served-model-name "$alias" --tensor-parallel-size "$tp"
  --max-model-len "$maxlen" --max-num-seqs 1 --max-num-batched-tokens 1024
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.90}" --dtype float16 --reasoning-parser qwen3
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-prompt-tokens-details
  --no-enable-prefix-caching )
[[ "$kv" != "f16" ]] && args+=( --kv-cache-dtype "$kv" )
[[ "$mtp" != "0" ]] && args+=( --speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$mtp}" )
[[ -n "${EXTRA_VLLM_ARGS:-}" ]] && args+=( ${EXTRA_VLLM_ARGS} )

echo "TP$tp nightly bench: MTP=$mtp KV=$kv maxlen=$maxlen gpus=$gpu suite=$(basename "$suite")"
printf '%s\n' "${args[@]}" > "$out/server-args.txt"

dockerc run -d --name "$name" \
  --device /dev/dri --group-add 44 --group-add 992 --ipc=host \
  -v /dev/dri/by-path:/dev/dri/by-path:ro \
  -v "$models_root:$models_root" \
  -p "127.0.0.1:$port:8000" \
  -e CCL_ZE_IPC_EXCHANGE=sockets \
  ${VLLM_XPU_GRAPH:+-e VLLM_XPU_ENABLE_XPU_GRAPH="$VLLM_XPU_GRAPH"} \
  -e ZE_AFFINITY_MASK="$gpu" \
  -e VLLM_NO_USAGE_STATS=1 -e VLLM_CACHE_ROOT="$cache_root" \
  -e TORCHINDUCTOR_CACHE_DIR="$cache_root/inductor" \
  -e TRITON_CACHE_DIR="$cache_root/triton" \
  -e XDG_CACHE_HOME="$cache_root/xdg" \
  --shm-size 16g \
  "$IMAGE" "${args[@]}" > "$out/container-id.txt"

cleanup() {
  dockerc logs "$name" > "$out/server.log" 2>&1 || true
  dockerc rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 240); do
  curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break
  state=$(dockerc inspect --format '{{.State.Running}}' "$name" 2>/dev/null || echo false)
  [[ "$state" == "true" ]] || { echo "container died; log tail:" >&2; dockerc logs --tail 40 "$name" >&2 || true; exit 2; }
  sleep 5
done
curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 || { echo 'health timeout' >&2; exit 2; }

dockerc exec "$name" python3 -c 'import vllm, torch; print("vllm", vllm.__version__); print("torch", torch.__version__)' > "$out/stack-versions.txt" 2>&1 || true
echo "healthy; benching"

"$venv/bin/python" "$repo/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:$port" --model "$alias" --api-mode chat \
  --suite "$suite" --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 900 \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}' \
  --out "$out/bench.json" > "$out/bench.stdout.log" 2>&1
bench_rc=$?
echo "bench_rc=$bench_rc"

"$venv/bin/python" - "$out/bench.json" <<'PY'
import json, statistics, sys
d = json.load(open(sys.argv[1]))
rows = d.get("rows", [])
dec = sorted(99.0/(r["chunk_offsets_s"][99]-r["chunk_offsets_s"][0])
             for r in rows if len(r.get("chunk_offsets_s") or []) >= 100)
ttft = sorted(r["ttft_s"] for r in rows if r.get("ttft_s"))
pt = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
out = {"decode_valid_rows": len(dec), "total_rows": len(rows)}
if dec: out["decode_median_tok_s"] = round(statistics.median(dec), 4)
if ttft: out["ttft_median_s"] = round(statistics.median(ttft), 4)
if pt: out["prompt_tokens_median"] = int(statistics.median(pt))
pf = sorted((r["prompt_tokens"]/r["ttft_s"]) for r in rows
            if r.get("ttft_s") and r.get("prompt_tokens"))
if pf: out["prefill_tok_s_median"] = round(statistics.median(pf), 1)
out["cached_tokens_all_zero"] = all((r.get("cached_tokens") or 0) == 0 for r in rows)
out["output_sha256"] = {r["prompt_id"]: r.get("sha256") for r in rows}
print(json.dumps({k: v for k, v in out.items() if k != "output_sha256"}))
open(sys.argv[1] + ".summary.json", "w").write(json.dumps(out, indent=1) + "\n")
PY
