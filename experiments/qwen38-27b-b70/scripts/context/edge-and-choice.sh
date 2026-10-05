#!/usr/bin/env bash
# Client for MU_MODE=serve_run on the full 262,144-token window: the one-step choice probe on the fresh server, recall
# asked the way an application asks (chat form, thinking off), recall with ordinary words around the codes, and the
# longest prompt that still answers every code (the first run answered at 200,000 tokens and not at 250,000).
# Needs BASE_URL, MODEL_NAME, OUT_DIR. notes/2026-10-05-context-window-prereg.md
set -u
S=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$HOME/.venvs/vllm-xpu/bin/python}
probe() { name=$1; shift; curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "server gone before $name"; exit 3; }; "$PY" "$S/qwen38-fp8-long-context-probe.py" --base-url "$BASE_URL" --model "$MODEL_NAME" --out "$OUT_DIR/$name.json" "$@" 2>&1 | tee "$OUT_DIR/$name.log"; }
"$PY" "$S/qwen38-fp8-one-step-choice-probe.py" --base-url "$BASE_URL" --model "$MODEL_NAME" --out "$OUT_DIR/choice.json" 2>&1 | tee "$OUT_DIR/choice.log" | tail -n 3
probe chat-recall --api chat --lengths 8000,30000,120000
probe prose-recall --api chat --style prose --lengths 30000,120000,200000
probe edge --lengths 200000,250000 --one-ledger --bisect 200000,250000,${EDGE_STEP:-1600}
# the two lengths either side of the edge again, in chat form and with ordinary words
read -r LOW HIGH < <("$PY" -c "import json,sys; e=json.load(open(sys.argv[1])).get('edge') or {}; print(e.get('longest_all_correct',200000), e.get('shortest_not_all_correct',250000))" "$OUT_DIR/edge.json")
probe edge-chat --api chat --one-ledger --lengths "$LOW,$HIGH"
probe edge-prose --api chat --style prose --one-ledger --lengths "$LOW,$HIGH,250000"
