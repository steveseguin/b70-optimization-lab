#!/usr/bin/env bash
# Campaign 16 diagnostic (registered in the lab note, "Prepended diagnostic"): why did the notes calls of XR6/FAp
# miss the prefix cache (2-4%) while their prompts are 99.95% continuations of the main calls'?
# One real ~10K-token prompt (FAp's, saved) replayed five ways against a fresh server; cached_tokens tells.
# S1: thinking-off changes the tokenized prompt server-side -> R3 misses.  S2: request-field keying -> R4 misses.
# Stops Gemma for the window and restores it; the server starts once and is stopped gracefully. No GPU fault, no arms.
set -uo pipefail
O=/mnt/fast-ai/bench-results/context-longrun-20261012
D=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign16
LAB=/home/steve/b70-optimization-lab
PORT=18196
SRV=$O/server/tp2-w262144-c16diag
say() { printf '### %(%H:%M:%S)T %s\n' -1 "$*"; }
avail() { awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo; }

say "diag start; MemAvailable $(avail) MiB"
curl -fsS -m 5 http://127.0.0.1:8000/v1/frontdoor/status >/dev/null 2>&1 && {
  sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service; say "Gemma stopped"; }
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | awk '{s+=$1} END {print s+0}')
  [[ -z $used || $used -lt 2000 ]] && break; sleep 5
done
say "cards free; MemAvailable $(avail) MiB"
systemctl --user reset-failed ctx-fp8-tp2-server 2>/dev/null
systemd-run --user --unit=ctx-fp8-tp2-server --collect -p WorkingDirectory=$LAB \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port $PORT \
  --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
  --tp 2 --mem 0.95 --max-model-len 262144 --batched 832 --fa-verify-rows --mtp 5 --draft-int4 \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
  --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
  --serve-arg=--enable-auto-tool-choice --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 \
  --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
  --serve-arg=--prefix-cache-retention-interval=13312 \
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 2>&1 | tail -1
for i in $(seq 1 120); do
  curl -fsS -m 3 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { say "server ready after ~$((i*15)) s"; break; }
  systemctl is-failed -q ctx-fp8-tp2-server && { say "server unit failed; see journal"; exit 1; }
  sleep 15
done
curl -fsS -m 3 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 || { say "server never ready"; exit 1; }

python3 - "$PORT" "$D/main_body.json" "$D/notes_body.json" "$D/diag-c16.json" <<'PY'
import json, sys, urllib.request
port, mainf, notesf, outf = sys.argv[1:5]
main = json.load(open(mainf)); notes = json.load(open(notesf))
def call(body, tag):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    u = r.get("usage") or {}
    det = u.get("prompt_tokens_details") or {}
    return {"tag": tag, "prompt_tokens": u.get("prompt_tokens"), "cached_tokens": det.get("cached_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "finish": (r.get("choices") or [{}])[0].get("finish_reason")}
base = dict(main, max_tokens=8)          # tiny replies: this measures the read, not the write
results = []
results.append(call(base, "R1 main, thinking on (warms)"))
results.append(call(base, "R2 repeat of R1 (sanity: expect ~full hit)"))
r3 = dict(base, chat_template_kwargs={"enable_thinking": False})
results.append(call(r3, "R3 same prompt, thinking off (S1 test)"))
results.append(call(base, "R4 repeat of R1 again (control after R3)"))
r5 = dict(base, max_tokens=4096)
results.append(call(r5, "R5 same prompt, different max_tokens (S2 test)"))
nb = dict(notes, max_tokens=8)
results.append(call(nb, "R6 the real notes call, thinking off"))
results.append(call(nb, "R7 repeat of R6 (its own cache)"))
json.dump(results, open(outf, "w"), indent=1)
for r in results:
    print(f"{r['tag']:<48} prompt={r['prompt_tokens']:>7} cached={r['cached_tokens']:>7} gen={r['completion_tokens']}")
PY
say "probe done; stopping the server"
systemctl --user stop ctx-fp8-tp2-server 2>/dev/null
for i in $(seq 1 40); do systemctl is-active -q ctx-fp8-tp2-server || break; sleep 5; done
sudo -A systemctl start gemma4-26b-q8-quad-backends.service gemma4-26b-q8-quad-frontdoor.service
say "Gemma restored; diag complete"
