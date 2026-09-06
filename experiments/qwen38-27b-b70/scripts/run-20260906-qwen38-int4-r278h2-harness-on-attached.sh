#!/usr/bin/env bash
# R278h2: the R278h attached-run server is still booting (its wrapper's health loop broke before the container existed);
# wait for it on port 18134, save its inspect record, run the harness c16/c32 x2, stop it.
set -uo pipefail
out=/mnt/fast-ai/bench-results/qwen38-int4-c32-request-shape-ab-20260906-r278h-mtp4; port=18134; name=qwen38-int4-r278h-profile; RUN=r278h
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$out/campaign.log"; }
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || { sleep 5; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; }; sleep 15; done
if (( ok )); then
  log "healthy (attached run)"; docker inspect "$name" > "$out/container-inspect.json" 2>/dev/null; mkdir -p "$out/ladder"
  python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url "http://127.0.0.1:$port" --model "$RUN" --api-mode completions \
    --suite /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json --concurrency 16,32 --repeats 2 --max-tokens 128 \
    --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity \
    --out "$out/ladder/ladder.json" > "$out/ladder/ladder.stdout" 2>&1; log "harness exit $?"
  python3 /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/summarize-int4-ladders-repeats.py "$out" 2>&1 | tee -a "$out/campaign.log"
else log "ABORT: attached server did not become healthy"; fi
docker stop -t 120 "$name" >/dev/null 2>&1 || true; log "campaign complete (h2)"
