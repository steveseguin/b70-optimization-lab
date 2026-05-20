#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-/mnt/fast-ai/bench-results/minimax-m27-b70-89tps}"

printf 'outdir=%s\n' "$OUTDIR"
find "$OUTDIR" -maxdepth 1 -name 'vllm-minimax-m27-autoround-*.json' ! -name '*.runtime.json' -printf '%T@ %p\n' \
  | sort -n | while read -r _ json; do
    log="${json%.json}.log"
    total="$(jq -r '.tokens_per_second // empty' "$json")"
    line="$(rg 'Throughput:' "$log" 2>/dev/null | tail -1 || true)"
    output="$(awk '{for (i=1; i<=NF; i++) if ($i == "output") print $(i-1)}' <<<"$line")"
    kv="$(rg 'GPU KV cache size:' "$log" | tail -1 | sed 's/^.*GPU KV cache size: //;s/ tokens.*//' || true)"
    avail="$(rg 'Available KV cache memory:' "$log" | tail -1 | sed 's/^.*Available KV cache memory: //' || true)"
    markers=0
    if rg -q 'Using llm-scaler XPU INT4 MiniMax logits WS decode path' "$log"; then
      markers=$((markers + 1))
    fi
    if rg -q 'Skipping communicator graph-capture context for XpuCommunicator' "$log"; then
      markers=$((markers + 1))
    fi
    printf '%s total=%s output=%s kv_tokens=%s kv_mem=%s markers=%s\n' \
      "$(basename "$json")" "$total" "${output:-unknown}" "${kv:-unknown}" "${avail:-unknown}" "$markers"
  done
