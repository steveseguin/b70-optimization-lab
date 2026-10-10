#!/usr/bin/env bash
# One-card (card 0) profiling campaign, 2026-10-10: every 1-2 card package or local model, one JSON per entry via
# tools/profile-run.sh. The Gemma LAN service stays on card 1 except for the two 27B vLLM entries, which need the host
# RAM (it is restored after them). Logs: data/profiles/<day>/campaign.log
set -uo pipefail
repo=/home/steve/b70-optimization-lab; cd "$repo"
day=$(date -u +%Y-%m-%d); out="$repo/data/profiles/$day"; mkdir -p "$out"; log="$out/campaign.log"
exec > >(tee -a "$log") 2>&1
set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; set -u
ND=/home/steve/src/llama.cpp-neural-download-20260822/build-sycl-aot-bmg-g31/bin/llama-server
M=/mnt/fast-ai/llm-models
ask=/tmp/claude-1000/-home-steve/a8e35385-b8e9-40ff-a46b-33dd51af5bca/scratchpad/askpass.sh
common_env=(--env ONEAPI_DEVICE_SELECTOR=level_zero:0 --env ZES_ENABLE_SYSMAN=1 --env PATH="$PATH" --env LD_LIBRARY_PATH="$LD_LIBRARY_PATH")
stamp() { echo "[campaign $(date +%T)] $*"; }
have() { [[ -f "$out/$1.json" ]] && { stamp "skip $1 (exists)"; return 0; }; return 1; }
llama() { # label alias users ctx model-file [extra llama args...]
  local label=$1 alias=$2 users=$3 ctx=$4 file=$5; shift 5
  have "$label" && return
  stamp "start $label"
  timeout 2400 tools/profile-run.sh --label "$label" --model "$alias" --users "$users" --load-seconds 40 --canary "${common_env[@]}" \
    -- "$ND" -m "$file" --alias "$alias" --host 127.0.0.1 --port 19350 -ngl 99 -c "$ctx" --parallel "$users" -b 2048 -ub 1024 -fa on --jinja --reasoning off --cache-ram 512 "$@" | tail -2 | cut -c1-400
}
compose() { # label pkgdir modeldir modelid users
  local label=$1 pkg=$2 mdir=$3 mid=$4 users=$5
  have "$label" && return
  stamp "start $label (compose one-gpu)"
  local cache="/mnt/fast-ai/bench-results/profile-cache/$label"; mkdir -p "$cache"
  ( sleep 20; scripts/apply-container-noswap.sh --name-prefix "profile-$label" --memory 9g >/dev/null 2>&1 || true ) &
  timeout 3000 tools/profile-run.sh --label "$label" --model "$mid" --users "$users" --load-seconds 40 --canary --no-cache-field --ready-timeout 1500 \
    --env MODEL_DIR="$mdir" --env PORT=19350 --env VLLM_CACHE_DIR="$cache" --env CONTAINER_NAME="profile-$label" \
    -- docker compose -f "$repo/packages/$pkg/compose.yaml" up --abort-on-container-exit one-gpu | tail -2 | cut -c1-400
  docker ps -q --filter "name=profile-$label" | xargs -r docker stop -t 30 >/dev/null 2>&1
  docker ps -aq --filter "name=profile-$label" | xargs -r docker rm >/dev/null 2>&1
}
gemma() { SUDO_ASKPASS=$ask timeout 600 scripts/gemma4-26b-two-b70-recipe.sh "$1" 2>&1 | tail -1; }

stamp "=== llama.cpp 9fee29e entries (Gemma service stays up on card 1) ==="
llama lfm25-26b-q8-b70-nd9fee29e-p4 lfm25 4 32768 $M/lfm2.5-2.6b-q8/LFM2.5-2.6B-Q8_0.gguf
llama ornith-15-9b-q8-b70-nd9fee29e-p4 ornith9b 4 32768 $M/ornith-1.5-9b-q8/Ornith-1.5-9B-Q8_0.gguf
llama qwen35-9b-q8-gguf-nd9fee29e-p4 qwen35-9b-q8 4 32768 $M/qwen35-9b-q8-gguf/Qwen3.5-9B-Q8_0.gguf
llama qwen36-27b-q8-gguf-nd9fee29e-p2 qwen36-27b-q8 2 32768 $M/qwen3.6-27b-q8_0-gguf/Qwen3.6-27B-Q8_0.gguf
llama qwen38-27b-q4km-gguf-nd9fee29e-p2 qwen38-27b-q4km 2 32768 $M/qwen3.8-27b-gguf/Qwen3.8-27B-Q4_K_M.gguf
llama qwen38-27b-q8-gguf-nd9fee29e-p2 qwen38-27b-q8 2 32768 $M/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf

stamp "=== small vLLM packages (compose one-gpu, container capped at 9g no swap; Gemma stays up) ==="
compose qwen35-9b-fp8-b70-one-gpu-p8 qwen35-9b-fp8-b70 $M/qwen35-9b-fp8-dynamic qwen35-9b-fp8 8
compose qwen35-9b-w4a16-b70-one-gpu-p8 qwen35-9b-w4a16-b70 $M/qwen35-9b-w4a16 qwen35-9b-w4a16 8
compose qwen35-4b-w4a16-b70-one-gpu-p8 qwen35-4b-w4a16-b70 $M/qwen35-4b-w4a16 qwen35-4b-w4a16 8

stamp "=== 27B vLLM entries: pause the Gemma service for host RAM ==="
SUDO_ASKPASS=$ask sudo -A systemctl stop gemma4-26b-q8-quad-backends.service
compose qwen38-27b-int4-fixed-k-one-gpu-p4 qwen38-27b-int4-fixed-k-tp2-b70 $M/qwen3.8-27b-int4-autoround-gptq-relabel qwen38-27b-int4 4
if ! have qwen38-27b-fp8-tp1-b70-recommended-p1; then
  stamp "start qwen38-27b-fp8-tp1 (serve.py recommended)"
  st="/mnt/fast-ai/bench-results/profile-cache/fp8-tp1-state-$(date +%s)"
  timeout 3000 tools/profile-run.sh --label qwen38-27b-fp8-tp1-b70-recommended-p1 --model qwen38-27b-fp8 --users 1 --load-seconds 40 --canary --no-cache-field --ready-timeout 1500 \
    -- python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir $M/qwen3.8-27b-fp8 --state-dir "$st" --port 19350 --gpu 0 --profile recommended | tail -2 | cut -c1-400
  docker ps -q --filter "name=neural-fp8-tp1" | xargs -r docker stop -t 30 >/dev/null 2>&1
fi
stamp "restore Gemma service (throughput-card1)"
gemma throughput-card1
stamp "=== campaign done ==="
python3 tools/profiles-summary.py "$out"
