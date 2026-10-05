#!/usr/bin/env python3
"""Tiny fake OpenAI-compatible server for wiring tests (no model, no GPU).

  fake_openai_server.py [PORT]   (default 18199; prints "listening <port> pid <pid>")

/v1/models lists one model. /v1/chat/completions answers with a scripted bash tool call
when the request carries tools: `next` until the stream ends, then write /app/answers.json
with the answers a perfect agent would give (parsed from the stream text in the request, so
a v2 task scores 1.0 unless a rule voids it; FAKE_PLAN=legacy writes an empty {} as before),
then the submit command (also when `next` was refused with "NOT RUN": it answers from what it has).
FAKE_PLAN=violate (after the first item) tries `next > file`
(must be refused) and writes one SET value / three counter names to /app/stash.txt (must
void a memory-only run); FAKE_PLAN=inline puts a value inside an inline python command only
(must NOT void: checks that the harness does not leave command text in files).
FAKE_PLAN=improved-fold | improved-probe (+ FAKE_CORRUPT=1): scripted clm_improved agent on ledger
tasks (fold items into /tmp/.live_ctx/STATE.txt; see plan_improved). FAKE_THINKCAP=1: every tool
request without continue_final_message gets a "length" reply with thinking only, so the
improved agent's think-cap continuation (continue_final_message) is exercised.
FAKE_REASONING=1: every tool-call reply carries reasoning_content (to check that the harness strips
earlier thinking; the request log has asst_with_reasoning per request).
FAKE_PLAN=improved-ctxfold: writes a buggy /tmp/.live_ctx/FOLD.py first (ctxfold must refuse it),
then a correct one, and folds every item with `ctxfold`. Without tools (e.g. a summary request) it
returns fixed text. /v1/completions returns fixed text. Usage numbers are rough
(chars/4) so the harness's tokenizer calibration has something to read.
"""
import json, os, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = os.environ.get("FAKE_MODEL", "qwen38-27b-fp8")


def _solve(text):
    """Answers a perfect agent would give, from the stream text the stub has seen."""
    kv, led, gets = {}, {}, []
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r"^SET (k-[0-9a-f]+) = (.*)$", ln)
        if m:
            kv[m.group(1)] = m.group(2).strip(); continue
        m = re.match(r"^(SET|ADD|DEL) ([a-z]+[0-9]{2})(?: (-?[0-9]+))? \| memo:", ln)
        if m:
            op, nm, v = m.group(1), m.group(2), m.group(3)
            if op == "SET": led[nm] = int(v)
            elif op == "ADD": led[nm] = led.get(nm, 0) + int(v)
            else: led.pop(nm, None)
            continue
        m = re.match(r"^(?:GET|QUERY) (\S+)$", ln)
        if m:
            gets.append(m.group(1)); continue
        m = re.match(r"^([a-z]+[0-9]{2}) (-?[0-9]+)$", ln)   # a pinned-state line "name value"
        if m:
            led[m.group(1)] = int(m.group(2))
    return {g: kv.get(g, led.get(g)) for g in gets}

FOLD = r"""python3 - <<'EOF'
import re
p = '/tmp/.live_ctx/LIVE_CTX_MAIN.txt'; sp = '/tmp/.live_ctx/STATE.txt'
s = open(p).read()
st = {}
try:
    for ln in open(sp).read().splitlines():
        a = ln.split()
        if len(a) == 2:
            st[a[0]] = int(a[1])
except FileNotFoundError:
    pass
parts = re.split(r'(\[\[CTX_TURN \d+ [^\]]*\]\])', s)
out, n = [parts[0]], 0
for i in range(1, len(parts), 2):
    h, b = parts[i], (parts[i + 1] if i + 1 < len(parts) else '')
    if re.match(r'\s*ITEM \d+/\d+ \((UPDATE|SET)\)', b):
        for m in re.finditer(r'^(SET|ADD|DEL) ([a-z]+[0-9]{2})(?: (-?[0-9]+))? \| memo:', b, re.M):
            op, nm, v = m.groups()
            if op == 'SET': st[nm] = int(v)
            elif op == 'ADD': st[nm] = st.get(nm, 0) + int(v)
            else: st.pop(nm, None)
        n += 1
        continue
    if 'PINNED STATE' in b or 'QUERY ' in b:
        out += [h, b]
open(sp, 'w').write(''.join('%s %d\n' % kv for kv in st.items()))
open(p, 'w').write(''.join(out))
print('folded %d items, state %d counters' % (n, len(st)))
EOF"""


def plan_improved(msgs, mode):
    """Scripted agent for clm_improved checks (ledger tasks). improved-fold: fold every item
    right after it arrives; improved-probe: first run `next` again (the room check must refuse
    it), fold on "NOT RUN". FAKE_CORRUPT=1: after the first fold, append a bad line to STATE.txt."""
    tools = [str(m.get("content") or "") for m in msgs if m.get("role") == "tool"]
    last = tools[-1] if tools else ""
    alltext = "\n".join(str(m.get("content") or "") for m in msgs[2:] if m.get("role") in ("tool", "user"))
    unfolded = any(re.match(r"ITEM \d+/\d+ \((UPDATE|SET)\)", t) for t in tools)
    if "answers.json written" in last:
        return "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
    if "This was the last item" in alltext:
        if unfolded:
            return FOLD
        return ("cat > /app/answers.json <<'EOF'\n" + json.dumps(_solve(alltext)) + "\nEOF\necho answers.json written")
    if os.environ.get("FAKE_CORRUPT") == "1" and last.startswith("folded") and "stub-corrupt-done" not in alltext:
        return "echo 'GARBAGE LINE' >> /tmp/.live_ctx/STATE.txt; echo stub-corrupt-done"
    if "NOT RUN" in last:
        return FOLD
    if last.startswith("ITEM "):
        return "next" if mode == "improved-probe" else FOLD
    return "next"


GOOD_FOLD = r"""import re
def _parse(state):
    st = {}
    for ln in state.splitlines():
        a = ln.split()
        if len(a) == 2:
            st[a[0]] = int(a[1])
    return st
def fold(state, lines):
    st, t = _parse(state), {}
    for ln in lines:
        op, nm, v = re.match(r"^(SET|ADD|DEL) (\S+)(?: (-?\d+))? \| memo:", ln).groups()
        if op == "SET": st[nm] = int(v)
        elif op == "ADD": st[nm] = st.get(nm, 0) + int(v)
        else: st.pop(nm, None)
        t[op] = t.get(op, 0) + 1
    return "".join("%s %d\n" % kv for kv in st.items()), t
def selftest():
    s, _ = fold("", ["SET a1 5 | memo: x", "ADD a1 2 | memo: x", "SET b2 1 | memo: x", "DEL b2 | memo: x"])
    assert _parse(s) == {"a1": 7}, s
    return ["SET", "ADD", "DEL"]
"""
# the seed-1 bug of 2026-10-05 (DEL popped the op word, not the counter): selftest must catch it
BAD_FOLD = GOOD_FOLD.replace("else: st.pop(nm, None)", "else: st.pop(op, None)")


def plan_ctxfold(msgs):
    tools = [str(m.get("content") or "") for m in msgs if m.get("role") == "tool"]
    last = tools[-1] if tools else ""
    alltext = "\n".join(str(m.get("content") or "") for m in msgs[2:] if m.get("role") in ("tool", "user"))
    unfolded = any(re.match(r"ITEM \d+/\d+ \((UPDATE|SET)\)", t) for t in tools)
    write = lambda src: "cat > /tmp/.live_ctx/FOLD.py <<'FOLDEOF'\n" + src + "FOLDEOF\nctxfold"
    if "answers.json written" in last:
        return "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
    if "ctxfold: REFUSED" in last:
        return write(GOOD_FOLD)
    if unfolded:
        return write(BAD_FOLD) if "ctxfold:" not in alltext else "ctxfold"
    if "This was the last item" in alltext:
        return ("cat > /app/answers.json <<'EOF'\n" + json.dumps(_solve(alltext)) + "\nEOF\necho answers.json written")
    return "next"


def plan(msgs):
    """Scripted agent. FAKE_PLAN: honest (default) | violate | inline (see module doc)."""
    seen = [str(m.get("content") or "") for m in msgs if m.get("role") in ("tool", "user")
            and m is not msgs[1]]  # skip the task prompt (it names the submit command)
    tools = "\n".join(seen)
    mode = os.environ.get("FAKE_PLAN", "honest")
    if mode == "improved-ctxfold":
        return plan_ctxfold(msgs)
    if mode.startswith("improved"):
        return plan_improved(msgs, mode)
    if "answers.json written" in tools:
        return "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
    last_tool = next((str(m.get("content") or "") for m in reversed(msgs) if m.get("role") == "tool"), "")
    if "STREAM END" in tools or "This was the last item" in tools or last_tool.startswith("NOT RUN"):
        ans = _solve(tools) if mode != "legacy" else {}
        return ("cat > /app/answers.json <<'EOF'\n" + json.dumps(ans) + "\nEOF\necho answers.json written")
    n_items = tools.count("ITEM ")
    if mode in ("violate", "inline") and n_items >= 1 and "stub-probe-done" not in tools:
        m = re.search(r"^SET k-[0-9a-f]+ = (.*)$", tools, re.M)
        names = re.findall(r"^(?:SET|ADD|DEL) ([a-z]+[0-9]{2})", tools, re.M)[:3]
        payload = m.group(1) if m else " ".join(names)
        if mode == "violate":   # tries the blocked route, then stores one value in a file
            return ("next > /app/copy.txt; echo rc=$?; echo '" + payload + "' > /app/stash.txt; "
                    "echo stub-probe-done")
        return ("python3 - <<'EOF'\nprint(len('" + payload + "'))\nEOF\necho stub-probe-done")
    return "next"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        sys.stderr.write("fake: " + (a[0] % a[1:]) + "\n")

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send({"object": "list", "data": [{"id": MODEL, "object": "model", "max_model_len": int(os.environ.get("FAKE_MAX_MODEL_LEN", "262144"))}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        msgs = req.get("messages") or []
        lt = next((str(m.get("content") or "") for m in reversed(msgs) if m.get("role") == "tool"), "")
        sys.stderr.write("fake-req: " + json.dumps({k: v for k, v in req.items()
                         if k not in ("messages", "tools")} | {"n_messages": len(msgs),
                         "has_tools": bool(req.get("tools")), "last_tool_head": lt[:60],
                         "last_tool_tail": lt[-200:],
                         # assistant turns before the newest message that still carry thinking text
                         "asst_with_reasoning": sum(1 for m in msgs[:-1] if m.get("role") == "assistant"
                                                    and (m.get("reasoning_content") or m.get("reasoning")))}) + "\n")
        pt = sum(len(json.dumps(m)) for m in msgs) // 4 or 1
        usage = {"prompt_tokens": pt, "completion_tokens": 12, "total_tokens": pt + 12}
        base = {"id": "fake-%d" % time.time_ns(), "created": int(time.time()), "model": MODEL, "usage": usage}
        if self.path.endswith("/completions") and "chat" not in self.path:
            return self._send({**base, "object": "text_completion",
                               "choices": [{"index": 0, "text": "OK", "finish_reason": "stop"}]})
        cont = bool(req.get("continue_final_message"))
        if req.get("tools") and os.environ.get("FAKE_THINKCAP") == "1" and not cont:
            # emulate a reply cut by max_tokens inside the thinking: no content, no tool call
            msg = {"role": "assistant", "content": None,
                   "reasoning_content": "stub thinking that runs out of tokens",
                   "reasoning": "stub thinking that runs out of tokens"}
            usage["completion_tokens"] = int(req.get("max_tokens") or 0)
            return self._send({**base, "object": "chat.completion",
                               "choices": [{"index": 0, "message": msg, "finish_reason": "length"}]})
        if req.get("tools"):
            cmd = plan(msgs)
            msg = {"role": "assistant", "content": "THOUGHT: scripted stub step.",
                   "tool_calls": [{"id": "call_%d" % time.time_ns(), "type": "function",
                                   "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}]}
            fr = "tool_calls"
            if os.environ.get("FAKE_REASONING") == "1":   # replies carry thinking the harness must strip later
                msg["reasoning_content"] = "stub thinking for call %d" % len(msgs)
        else:
            msg = {"role": "assistant", "content": "Stub summary: nothing to report."}
            fr = "stop"
        self._send({**base, "object": "chat.completion",
                    "choices": [{"index": 0, "message": msg, "finish_reason": fr}]})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18199
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"listening {port} pid {os.getpid()}", flush=True)
    srv.serve_forever()
