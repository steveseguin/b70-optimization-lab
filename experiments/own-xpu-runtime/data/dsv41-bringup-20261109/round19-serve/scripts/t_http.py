#!/usr/bin/env python3
"""HTTP tests of the DeepSeek LAN server (run against a started server). usage: t_http.py [base_url]"""
import json, sys, threading, time, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
W = "/home/steve/dsv41-work"
PP = "/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts"
RES = {}


def post(path, body, timeout=3600):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as f:
        return json.loads(f.read())


def stream(body, close_after=None):
    body = dict(body, stream=True, stream_options={"include_usage": True})
    r = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    f = urllib.request.urlopen(r, timeout=3600)
    out = {"reasoning": "", "content": "", "tool_calls": [], "finish": None, "usage": None, "timings": None, "chunks": 0, "error": None}
    buf = b""
    while True:
        b = f.read1(65536) if hasattr(f, "read1") else f.read(1024)
        if not b:
            break
        buf += b
        while b"\n\n" in buf:
            ln, buf = buf.split(b"\n\n", 1)
            if not ln.startswith(b"data: ") or ln == b"data: [DONE]":
                continue
            j = json.loads(ln[6:])
            if "error" in j:
                out["error"] = j["error"]
                continue
            if j.get("usage"):
                out["usage"], out["timings"] = j["usage"], j.get("timings")
            for c in j.get("choices", []):
                d = c["delta"]
                out["reasoning"] += d.get("reasoning_content") or ""
                out["content"] += d.get("content") or ""
                out["tool_calls"] += d.get("tool_calls") or []
                if c.get("finish_reason"):
                    out["finish"] = c["finish_reason"]
                out["chunks"] += 1
            if close_after and out["chunks"] >= close_after:
                f.close()
                return out
    return out


def ok(name, cond, info=""):
    RES[name] = bool(cond)
    print(f"{'PASS' if cond else 'FAIL'} {name} {info}", flush=True)


def tm(t):
    return f"(read {t['read_tokens']} in {t['read_s']:.2f} s, {t['answer_tokens']} at {t['answer_tok_per_s']} tok/s)" if t else ""


t0 = time.time()
while True:
    h = get("/health")
    if h["status"] == "ready":
        break
    if h["status"] == "fault" or time.time() - t0 > 1500:
        sys.exit(f"server not ready: {h}")
    time.sleep(5)
print("ready", h, flush=True)
M = "deepseek-v4.1-flash"

# 1. non-stream, thinking off
r = post("/v1/chat/completions", {"model": M, "messages": [{"role": "user", "content": "Say hello in five words."}], "enable_thinking": False, "max_tokens": 64})
c = r["choices"][0]
ok("chat_nothink", c["message"]["content"] and "reasoning_content" not in c["message"] and c["finish_reason"] == "stop", repr(c["message"]["content"][:80]) + " " + tm(r.get("timings")))

# 2. follow-up continues the held conversation (only the new turn is read)
msgs = [{"role": "user", "content": "Say hello in five words."}, {"role": "assistant", "content": c["message"]["content"]},
        {"role": "user", "content": "Now in French."}]
r2 = post("/v1/chat/completions", {"model": M, "messages": msgs, "enable_thinking": False, "max_tokens": 64})
t = r2["timings"]
ok("followup_nothink_continues", t["read_tokens"] < 20 and r2["usage"]["prompt_tokens_details"]["cached_tokens"] > 0, repr(r2["choices"][0]["message"]["content"][:80]) + " " + tm(t))

# 3. stream with thinking (new conversation -> engine reset)
s = stream({"model": M, "messages": [{"role": "user", "content": "What is 17 * 23? Answer with just the number."}], "max_tokens": 2048})
ok("stream_think", s["reasoning"] and "391" in s["content"] and s["finish"] == "stop" and s["usage"], f"reasoning {len(s['reasoning'])} chars, content {s['content'].strip()[:40]!r} {tm(s['timings'])}")
# 4. follow-up with thinking, client drops the thinking (server puts it back)
msgs = [{"role": "user", "content": "What is 17 * 23? Answer with just the number."}, {"role": "assistant", "content": s["content"]},
        {"role": "user", "content": "And 391 / 17?"}]
s2 = stream({"model": M, "messages": msgs, "max_tokens": 2048})
ok("followup_think_continues", s2["timings"] and s2["timings"]["read_tokens"] < 30 and "23" in s2["content"], f"{s2['content'].strip()[:40]!r} {tm(s2['timings'])}")

# 4b. a third turn with thinking: both earlier answers' thinking is put back (only the new turn is read)
msgs3 = msgs + [{"role": "assistant", "content": s2["content"]}, {"role": "user", "content": "And 23 * 17?"}]
s3 = stream({"model": M, "messages": msgs3, "max_tokens": 2048})
ok("third_turn_think_continues", s3["timings"] and s3["timings"]["read_tokens"] < 30 and "391" in s3["content"], f"{s3['content'].strip()[:40]!r} {tm(s3['timings'])}")

# 5. identity through the HTTP + tokenizer path: the raw code prompt vs the command-line answer (up to its end token)
pieces_prompt = open(f"{PP}/code.txt").read() if False else None
code_ids = [int(x) for x in open(f"{PP}/code-ids.txt").read().split()]
ref = [int(x) for x in open(f"{W}/runs/e57/code_plain-ids.txt").read().split()]
ref = ref[:ref.index(1) + 1] if 1 in ref else ref
tok = post("/tokenize", {"content": "x"})  # (warm)
# rebuild the prompt text from the server's own vocabulary: /v1/completions with the exact text
import subprocess, os
env = dict(os.environ, LD_LIBRARY_PATH="/home/steve/dsv41-serve/lib")
cfg = json.load(open("/home/steve/dsv41-serve/config.json"))
p = subprocess.run(["/home/steve/dsv41-serve/bin/tokhelper", cfg["gguf"]], input=b"V\n", capture_output=True, env=env)
lines = p.stdout.split(b"\n")
pieces = [bytes.fromhex(x.decode()) for x in lines[1:1 + int(lines[0].split()[1])]]
text = b"".join(pieces[i] for i in code_ids).decode()
ok("tokenizer_roundtrip_code", post("/tokenize", {"content": text})["tokens"] == code_ids)
r5 = post("/v1/completions", {"model": M, "prompt": text, "max_tokens": len(ref)})
got = post("/tokenize", {"content": r5["choices"][0]["text"]})["tokens"]
ref_text = b"".join(pieces[i] for i in ref if i != 1).decode("utf-8", "replace")
ok("code_identity_http", r5["choices"][0]["text"] == ref_text, f"{len(ref)} ref tokens, {r5['usage']['completion_tokens']} answered {tm(r5.get('timings'))}")

# 6. tools: a call, then the result, then the answer
tools = [{"type": "function", "function": {"name": "multiply", "description": "Multiply two integers exactly.",
          "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}}}]
q = [{"role": "user", "content": "Use the multiply tool to compute 1234 * 5678, then tell me the result."}]
r6 = post("/v1/chat/completions", {"model": M, "messages": q, "tools": tools, "max_tokens": 4096})
m6 = r6["choices"][0]["message"]
tc = (m6.get("tool_calls") or [None])[0]
ok("tool_call", tc and tc["function"]["name"] == "multiply" and r6["choices"][0]["finish_reason"] == "tool_calls", json.dumps(tc)[:160] + " " + tm(r6.get("timings")))
if tc:
    q2 = q + [{"role": "assistant", "content": m6.get("content"), "tool_calls": [tc]},
              {"role": "tool", "tool_call_id": tc["id"], "content": str(1234 * 5678)}]
    r7 = post("/v1/chat/completions", {"model": M, "messages": q2, "tools": tools, "max_tokens": 4096})
    ok("tool_result_answer", "7006652" in (r7["choices"][0]["message"]["content"] or "").replace(",", "") and r7["timings"]["read_tokens"] < 40,
       repr((r7["choices"][0]["message"]["content"] or "")[:80]) + " " + tm(r7.get("timings")))

# 7. stop string
r8 = post("/v1/chat/completions", {"model": M, "messages": [{"role": "user", "content": "Count from 1 to 20, separated by commas."}],
                                   "enable_thinking": False, "stop": ["7"], "max_tokens": 200})
ok("stop_string", "7" not in r8["choices"][0]["message"]["content"] and "6" in r8["choices"][0]["message"]["content"], repr(r8["choices"][0]["message"]["content"][:60]))

# 8. a client that leaves mid-answer: the answer stops, the server is free again
t1 = time.time()
s9 = stream({"model": M, "messages": [{"role": "user", "content": "Write a 2000-word story about a lighthouse."}], "enable_thinking": False, "max_tokens": 4000}, close_after=20)
for _ in range(60):
    h = get("/health")
    if not h["busy"]:
        break
    time.sleep(1)
ok("client_leaves", not h["busy"] and time.time() - t1 < 60, f"free after {time.time() - t1:.1f} s")

# 9. two clients at once: the second waits for the first, both answer
outs = {}
def one(k, txt):
    outs[k] = post("/v1/chat/completions", {"model": M, "messages": [{"role": "user", "content": txt}], "enable_thinking": False, "max_tokens": 64})
th = [threading.Thread(target=one, args=(k, f"Name a {w}.")) for k, w in ((0, "color"), (1, "fruit"))]
[x.start() for x in th]; [x.join() for x in th]
ok("two_clients", all(outs.get(k) and outs[k]["choices"][0]["message"]["content"] for k in (0, 1)),
   " | ".join(repr(outs[k]["choices"][0]["message"]["content"][:30]) for k in outs))

print("health", get("/health"))
print("SUMMARY", "ALL PASS" if all(RES.values()) else "FAILED: " + ", ".join(k for k, v in RES.items() if not v), flush=True)
