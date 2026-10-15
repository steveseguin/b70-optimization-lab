#!/usr/bin/env bash
# Identity check for the coalesced reordered-Q8_0 conversion on Gemma 4 26B A4B Q8 (registered 2026-10-15 in
# notes/2026-10-15-prefill-reorder-check.md). Same setup as gemma-prefill-check.sh: TEST servers on card 1 through the
# production launcher (service profile, one user, 32K), the LAN service on card 0 meanwhile, its throughput recipe
# restored at the end. The test servers use the LAN service's own settings (deterministic oneDNN matmul, prompt
# micro-batch 1024, no speculation, as the throughput recipe), one slot. The first attempt (19:16) lacked them: its
# servers were not run-to-run deterministic, and llama-server's logprob output aborts this build ("no logits").
#   verify  test build, LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=2: old and new conversion on every call, compared
#   prod    the production binary
#   new     test build, flag 1          (RUNS default: verify, prod-a, new-a, prod-b, new-b; prod-b is the control)
# Each: the 12-prompt realistic suite (512 tokens, greedy, no prompt cache), the 2K / 8K / 24K prompts (128 tokens,
# token ids), then the server's prompt rate on those prompts twice.        SUDO_ASKPASS set; under systemd-run --user
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
LAUNCH=/home/steve/llm-optimizations/scripts/serve-gemma4-26b-q8-production.sh
PROD=/home/steve/src/llama.cpp-gemma-c926-oneapi2026.1-compat/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
COPY=/home/steve/src/llama.cpp-gemma-c926-compat-q8deq-20261015/build-q8deq/bin/llama-server
OUT=${OUT:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/identity-q8deq-20261015}
SUITE=$LAB/repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json
LONG=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe/long-prompts.json
COMPARE_PY=$LAB/experiments/lfm25-24b-a2b-b70/scripts/compare_arrays.py
PORT=18120
UNIT=gemma-identity-srv
mkdir -p "$OUT"
log() { echo "### $(date +%T) $*"; }
START=$(date '+%Y-%m-%d %H:%M:%S')
restore() {
  systemctl --user stop $UNIT 2>/dev/null
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | grep -v "JSONDecode\|raise " | tail -3
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 || true
  log done
}
trap restore EXIT
log "moving the Gemma service to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2
for run in ${RUNS:-verify:copy:2 prod-a:prod:0 new-a:copy:1 prod-b:prod:0 new-b:copy:1}; do
  IFS=: read -r name build val <<< "$run"
  bin=$PROD; [[ $build == copy ]] && bin=$COPY
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  systemd-run --user --unit=$UNIT --collect -E GEMMA4_26B_PROFILE=service -E GPU_INDEX=1 -E PORT=$PORT \
    -E CTX_SIZE=32768 -E PARALLEL=1 -E GGML_SYCL_DNNL_DETERMINISTIC=1 -E LLAMA_PREFILL_UBATCH_SIZE=1024 \
    -E "EXTRA_LLAMA_ARGS=--parallel 1 --cache-ram 0 --ctx-checkpoints 0" -E LLAMA_SERVER="$bin" -E OUT_DIR="$OUT" -E LOG="$OUT/server-$name.log" \
    -E LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=$val bash -c "exec $LAUNCH > $OUT/launch-$name.log 2>&1" >/dev/null
  ok=0
  for i in $(seq 1 400); do
    curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "$name ($build, flag $val) ready after ${i}s"; ok=1; break; }
    systemctl --user is-active --quiet $UNIT || { log "$name server died"; tail -5 "$OUT/launch-$name.log"; break; }
    sleep 1
  done
  [[ $ok == 1 ]] || exit 1
  log "$name: suite (512 tokens)"
  python3 "$LAB/scripts/bench-openai-realistic-suite.py" --base-url "http://127.0.0.1:$PORT" \
    --model gemma4-26b-a4b-q8 --api-mode native --suite "$SUITE" \
    --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 --return-token-ids \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' --out "$OUT/suite-$name.json" \
    >/dev/null 2>"$OUT/suite-$name.err" || { log "$name suite failed"; tail -3 "$OUT/suite-$name.err"; }
  log "$name: long prompts (128 tokens), then the prompt rate twice"
  python3 - "$LONG" "http://127.0.0.1:$PORT" "$OUT/long-$name.json" "$name" <<'PYEOF'
import json, sys, urllib.request
prompts, base, out, name = json.load(open(sys.argv[1]))["prompts"], sys.argv[2], sys.argv[3], sys.argv[4]
def post(body):
    req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))
prompts = sorted(prompts, key=lambda p: len(p["prompt"]))
res = {"long": [], "rate": []}
for p in prompts:
    r = post({"prompt": p["prompt"], "n_predict": 128, "temperature": 0, "top_k": 1, "seed": 42, "cache_prompt": False,
              "return_tokens": True})
    res["long"].append({"id": p["id"], "tokens": r["tokens"], "prompt_n": r["timings"]["prompt_n"]})
for rep in (1, 2):
    for p in prompts:
        t = post({"prompt": p["prompt"], "n_predict": 1, "temperature": 0, "cache_prompt": False})["timings"]
        res["rate"].append({"id": p["id"], "rep": rep, "prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"],
                            "prompt_per_second": t["prompt_per_second"]})
        print(f'{name} {p["id"]} rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s', flush=True)
json.dump(res, open(out, "w"), indent=1)
PYEOF
  if [[ $name == verify ]]; then
    grep -a "Q8_0_REORDER_DEQ_VERIFY calls" "$OUT/server-$name.log" | sed 's/.*Q8_0_REORDER/Q8_0_REORDER/' | tail -2
    echo "mismatch lines: $(grep -ac 'Q8_0_REORDER_DEQ_VERIFY mismatch' "$OUT/server-$name.log")"
  fi
  systemctl --user stop $UNIT
  for _ in $(seq 1 60); do systemctl --user is-active --quiet $UNIT || break; sleep 1; done
done
log "suite: prod-a vs the others"
python3 "$COMPARE_PY" "$OUT/suite-prod-a.json" "$OUT"/suite-{prod-b,new-a,new-b,verify}.json 2>&1 | cut -c1-240
log "long prompts: prod-a vs the others"
python3 - "$OUT" <<'PYEOF'
import json, sys
d = sys.argv[1]
ref = {r["id"]: r["tokens"] for r in json.load(open(f"{d}/long-prod-a.json"))["long"]}
for name in ("prod-b", "new-a", "new-b", "verify"):
    try:
        cand = {r["id"]: r["tokens"] for r in json.load(open(f"{d}/long-{name}.json"))["long"]}
    except OSError:
        print(name, "missing"); continue
    same = [k for k in ref if cand.get(k) == ref[k]]
    print(f"{name}: {len(same)}/{len(ref)} long prompts token-identical to prod-a")
PYEOF
