#!/usr/bin/env bash
set -euo pipefail

# TP1 (single B70) benchmark for Qwen3.8-27B AutoRound INT4, one config per
# invocation. Boots vLLM directly (TP1 needs no oneCCL), runs the fixed
# realistic suite, records the conventional decode rate + prefill + TTFT.
# Diagnostic benchmark (not a sealed record). Fresh cache namespace per
# config under a shared TP1 cache root (MTP/KV fork compile_factors).
#
# Usage: run-20260822-qwen38-tp1-bench.sh MTP KV MAXLEN GPU PORT OUT_DIR SUITE
#   MTP: 0 (off) | 1 | 2 | 3   KV: f16 | fp8_e5m2
#   SUITE: path to a validation-suite.json (short realistic suite or a longkv depth suite)

mtp=${1:?}; kv=${2:?}; maxlen=${3:?}; gpu=${4:?}; port=${5:?}; out=${6:?}; suite=${7:?}
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
venv=/home/steve/.venvs/vllm-xpu
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
cache_root=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-tp1-bench-20260822
alias=qwen38-tp1
mkdir -p "$out" "$cache_root"

pgrep -af 'EngineCore|vllm serve' | grep -v pgrep >/dev/null && { echo 'a vLLM server is already running' >&2; exit 1; }
[[ -f "$suite" ]] || { echo "missing suite: $suite" >&2; exit 1; }

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu}"
export ZE_AFFINITY_MASK="$gpu"
export PYTHONPATH="$stage"
export LD_LIBRARY_PATH="$stage/vllm_xpu_kernels:$venv/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"
export VLLM_CACHE_ROOT="$cache_root"
export VLLM_NO_USAGE_STATS=1
export VLLM_XPU_ENABLE_XPU_GRAPH=1

args=( serve "$model" --host 127.0.0.1 --port "$port" --trust-remote-code
  --served-model-name "$alias" --tensor-parallel-size 1
  --max-model-len "$maxlen" --max-num-seqs 1 --max-num-batched-tokens 1024
  --gpu-memory-utilization 0.90 --dtype float16 --reasoning-parser qwen3
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-prompt-tokens-details
  --enforce-eager )
[[ "$kv" != "f16" ]] && args+=( --kv-cache-dtype "$kv" )
[[ "$mtp" != "0" ]] && args+=( --speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$mtp}" )

echo "TP1 bench: MTP=$mtp KV=$kv maxlen=$maxlen gpu=$gpu suite=$(basename "$suite")"
"$venv/bin/vllm" "${args[@]}" > "$out/server.log" 2>&1 &
srv=$!
cleanup() { kill "$srv" 2>/dev/null || true; sleep 3; pgrep -af 'EngineCore|vllm serve' | grep -v pgrep | awk '{print $1}' | xargs -r kill -9 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 240); do
  curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break
  kill -0 "$srv" 2>/dev/null || { echo "server died; see $out/server.log" >&2; tail -20 "$out/server.log" >&2; exit 2; }
  sleep 5
done
curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 || { echo 'health timeout' >&2; exit 2; }
echo "healthy; benching"

"$venv/bin/python" "$repo/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:$port" --model "$alias" --api-mode chat \
  --suite "$suite" --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 900 \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}' \
  --out "$out/bench.json" > "$out/bench.stdout.log" 2>&1
bench_rc=$?
echo "bench_rc=$bench_rc"

"$venv/bin/python" - "$out/bench.json" "$out/server.log" <<'PY'
import json, statistics, sys, re
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
# prefill: prompt_tokens / ttft per row (prefill throughput), median
pf = sorted((r["prompt_tokens"]/r["ttft_s"]) for r in rows
            if r.get("ttft_s") and r.get("prompt_tokens"))
if pf: out["prefill_tok_s_median"] = round(statistics.median(pf), 1)
# spec acceptance from server log
try:
    txt = open(sys.argv[2]).read()
    acc = [float(m) for m in re.findall(r"Mean acceptance length: ([0-9.]+)", txt)]
    if acc: out["mean_acceptance_length"] = round(statistics.median(acc), 2)
except OSError:
    pass
print(json.dumps(out))
open(sys.argv[1] + ".summary.json", "w").write(json.dumps(out, indent=1) + "\n")
PY
