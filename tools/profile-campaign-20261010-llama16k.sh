#!/usr/bin/env bash
# Follow-up to profile-campaign-20261010.sh: the llama.cpp entries again with 16K per slot (-c = slots x 16384) so the
# 8K prefill point fits, plus LFM2.5 (first attempt crashed the harness) . Run after the main campaign; skips entries that exist.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; cd "$repo"
day=$(date -u +%Y-%m-%d); out="$repo/data/profiles/$day"; mkdir -p "$out"; log="$out/campaign.log"
exec > >(tee -a "$log") 2>&1
set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; set -u
ND=/home/steve/src/llama.cpp-neural-download-20260822/build-sycl-aot-bmg-g31/bin/llama-server
M=/mnt/fast-ai/llm-models
common_env=(--env ONEAPI_DEVICE_SELECTOR=level_zero:0 --env ZES_ENABLE_SYSMAN=1 --env PATH="$PATH" --env LD_LIBRARY_PATH="$LD_LIBRARY_PATH")
stamp() { echo "[campaign16k $(date +%T)] $*"; }
have() { [[ -f "$out/$1.json" ]] && { stamp "skip $1 (exists)"; return 0; }; return 1; }
llama() { # label alias users model-file [extra]
  local label=$1 alias=$2 users=$3 file=$4; shift 4
  have "$label" && return
  stamp "start $label"
  timeout 2400 tools/profile-run.sh --label "$label" --model "$alias" --users "$users" --load-seconds 40 --canary "${common_env[@]}" \
    -- "$ND" -m "$file" --alias "$alias" --host 127.0.0.1 --port 19350 -ngl 99 -c $((users * 16384)) --parallel "$users" -b 2048 -ub 1024 -fa on --jinja --reasoning off --cache-ram 512 "$@" | tail -2 | cut -c1-400
}
llama lfm25-26b-q8-b70-nd9fee29e-16k-p4 lfm25 4 $M/lfm2.5-2.6b-q8/LFM2.5-2.6B-Q8_0.gguf
llama ornith-15-9b-q8-b70-nd9fee29e-16k-p4 ornith9b 4 $M/ornith-1.5-9b-q8/Ornith-1.5-9B-Q8_0.gguf
llama qwen35-9b-q8-gguf-nd9fee29e-16k-p4 qwen35-9b-q8 4 $M/qwen35-9b-q8-gguf/Qwen3.5-9B-Q8_0.gguf
llama nemotron-35-lightning-30b-a3b-nd9fee29e-16k-p4 nemotron-35-lightning-30b-a3b 4 $M/nemotron-3.5-lightning-30b-a3b-udq4km/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf
llama qwen36-27b-q8-gguf-nd9fee29e-16k-p2 qwen36-27b-q8 2 $M/qwen3.6-27b-q8_0-gguf/Qwen3.6-27B-Q8_0.gguf
llama qwen38-27b-q4km-gguf-nd9fee29e-16k-p2 qwen38-27b-q4km 2 $M/qwen3.8-27b-gguf/Qwen3.8-27B-Q4_K_M.gguf
llama qwen38-27b-q8-gguf-nd9fee29e-16k-p2 qwen38-27b-q8 2 $M/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf
stamp "=== llama 16k follow-up done ==="
python3 tools/profiles-summary.py "$out"
