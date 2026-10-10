#!/usr/bin/env python3
"""One profiling pass against any OpenAI-compatible chat endpoint, written as JSON.

Measures, with temperature 0 and distinct seeded prompts:
  decode_1user      : tok/s after the first token, 300-token prompt, 256 answer tokens (median of 3)
  prefill_*         : time to first token and prompt tok/s at 512 / 2048 / 8192-token prompts (cold, cache_prompt off)
  repeat_identical  : the same cold 3K prompt 3 times -> number of distinct answers (1 = repeat-deterministic)
  multi_user        : closed-loop aggregate at N concurrent clients (N = --users), 300-token prompts, 150 answer
                      tokens: prompt/completion/total tok/s, requests/s, mean latency; plus per-stream decode tok/s
                      with N streams started together (100-token prompts, 256 tokens)
  batch_identical   : the same prompt sent alone and N at once -> distinct answers (1 = batch-invariant on this prompt)
  canary            : optional, runs scripts/gemma4-text-canary.py (answer correctness) if --canary is given

usage: tools/profile-openai-endpoint.py --base http://127.0.0.1:19350 --model <id> --label <package-id> \
          --users 4 --out data/profiles/<package-id>.json [--canary] [--no-cache-field]
"""
import argparse, json, time, threading, http.client, urllib.parse, hashlib, random, statistics, subprocess, os, sys

WORDS = ["network", "server", "cache", "token", "model", "layer", "query", "memory", "device", "kernel", "stream",
         "batch", "prompt", "answer", "number", "letter", "window", "signal", "buffer", "thread", "user", "message",
         "order", "ticket", "refund", "login", "error", "update", "price", "delivery"]

def filler(n, seed):
    r = random.Random(seed); return " ".join(r.choice(WORDS) for _ in range(max(1, n)))

def prompt_chat(n_tokens, seed, task="lan"):
    q = {"lan": "In two sentences, what is a local area network? Then list five prime numbers.",
         "summ": "Summarize what kind of document this is in two sentences."}[task]
    return ("Below is a reference document. After it, answer the question.\n\n" + filler(n_tokens - 40, seed) +
            "\n\nQuestion: " + q)

def prompt_batch(n_tokens, seed):
    return ("You are a data-processing assistant. Classify the following chat message into one of: question, complaint, "
            "request, feedback, other. Then write one sentence explaining why, and extract any product words.\n\n"
            "Message: " + filler(n_tokens - 40, seed))

class Client:
    def __init__(self, base, model, cache_field=True):
        self.u = urllib.parse.urlsplit(base); self.model = model; self.cache_field = cache_field
    def stream(self, prompt, max_tokens, cache=True):
        c = http.client.HTTPConnection(self.u.hostname or "127.0.0.1", self.u.port, timeout=900)
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                "temperature": 0, "stream": True, "stream_options": {"include_usage": True}}
        if self.cache_field: body["cache_prompt"] = cache
        t0 = time.time(); c.request("POST", "/v1/chat/completions", body=json.dumps(body), headers={"Content-Type": "application/json"})
        r = c.getresponse(); ttft = None; t_first = None; text = []; usage = None; buf = b""; n = 0; tl = None
        while True:
            ch = r.read1(65536)
            if not ch: break
            buf += ch
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1); line = line.strip()
                if not line.startswith(b"data:") or line[5:].strip() == b"[DONE]": continue
                try: j = json.loads(line[5:])
                except Exception: continue
                if j.get("usage"): usage = j["usage"]
                for ch_ in j.get("choices", []):
                    d = ch_.get("delta", {}).get("content")
                    if d:
                        if ttft is None: t_first = time.time(); ttft = t_first - t0
                        text.append(d); n += 1; tl = time.time()
        wall = time.time() - t0; u = usage or {}
        ct = u.get("completion_tokens", n); pt = u.get("prompt_tokens")
        dec = (ct - 1) / (tl - t_first) if (t_first and tl and ct > 1 and tl > t_first) else None
        return {"status": r.status, "ttft": ttft, "wall": wall, "prompt_tokens": pt, "completion_tokens": ct,
                "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                "decode_tps": dec, "sha": hashlib.sha256("".join(text).encode()).hexdigest()[:12], "head": "".join(text)[:80]}
    def plain(self, prompt, max_tokens, cache=True):
        c = http.client.HTTPConnection(self.u.hostname or "127.0.0.1", self.u.port, timeout=900)
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0}
        if self.cache_field: body["cache_prompt"] = cache
        t0 = time.time(); c.request("POST", "/v1/chat/completions", body=json.dumps(body), headers={"Content-Type": "application/json"})
        r = c.getresponse(); d = json.loads(r.read()); u = d["usage"]
        txt = d["choices"][0]["message"]["content"]
        return {"wall": time.time() - t0, "prompt_tokens": u["prompt_tokens"], "completion_tokens": u["completion_tokens"],
                "sha": hashlib.sha256(txt.encode()).hexdigest()[:12]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--model", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--users", type=int, default=4); ap.add_argument("--out", required=True)
    ap.add_argument("--canary", action="store_true"); ap.add_argument("--no-cache-field", action="store_true")
    ap.add_argument("--load-seconds", type=float, default=40); ap.add_argument("--skip-8k", action="store_true")
    a = ap.parse_args()
    cl = Client(a.base, a.model, cache_field=not a.no_cache_field)
    res = {"label": a.label, "base": a.base, "model": a.model, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "users": a.users}
    # warm-up
    cl.stream(prompt_chat(100, 999), 16, cache=False)
    # decode, 1 user
    runs = [cl.stream(prompt_chat(300, 1000 + i), 256, cache=False) for i in range(3)]
    res["decode_1user"] = {"median_tps": statistics.median([r["decode_tps"] for r in runs if r["decode_tps"]]),
                           "runs": [{k: r[k] for k in ("decode_tps", "ttft", "completion_tokens", "sha")} for r in runs]}
    # prefill ladder
    res["prefill"] = {}
    for n in ([512, 2048] if a.skip_8k else [512, 2048, 8192]):
        r = cl.stream(prompt_chat(n, 2000 + n), 16, cache=False)
        res["prefill"][str(n)] = {"ttft_s": round(r["ttft"], 3) if r["ttft"] else None, "prompt_tokens": r["prompt_tokens"],
                                  "prompt_tps": round(r["prompt_tokens"] / r["ttft"], 1) if r["ttft"] and r["prompt_tokens"] else None}
    # repeat determinism (cold, high-entropy summary prompt)
    p = prompt_chat(3000, 4, "summ")
    reps = [cl.plain(p, 120, cache=False) for _ in range(3)]
    res["repeat_identical"] = {"distinct": len({r["sha"] for r in reps}), "shas": [r["sha"] for r in reps]}
    # batch identity: alone vs N at once (same prompt)
    alone = cl.plain(p, 120, cache=False)
    out = {}
    def one(i): out[i] = cl.plain(p, 120, cache=False)
    ths = [threading.Thread(target=one, args=(i,)) for i in range(a.users)]
    for t in ths: t.start()
    for t in ths: t.join()
    res["batch_identical"] = {"alone_sha": alone["sha"], "batch_shas": [out[i]["sha"] for i in range(a.users)],
                              "distinct_incl_alone": len({alone["sha"]} | {out[i]["sha"] for i in range(a.users)})}
    # per-stream decode with N streams together
    outs = {}
    def two(i): outs[i] = cl.stream(prompt_chat(100, 3000 + i), 256, cache=False)
    ths = [threading.Thread(target=two, args=(i,)) for i in range(a.users)]
    for t in ths: t.start()
    for t in ths: t.join()
    dts = [outs[i]["decode_tps"] for i in range(a.users) if outs[i]["decode_tps"]]
    res["decode_nusers"] = {"per_stream_median_tps": statistics.median(dts) if dts else None, "aggregate_tps": round(sum(dts), 1) if dts else None}
    # closed-loop load
    stats = {"req": 0, "prompt": 0, "completion": 0, "lat": 0.0, "errors": 0}; lock = threading.Lock()
    stop_at = time.time() + 5 + a.load_seconds
    def worker(w):
        i = 0
        while time.time() < stop_at:
            try:
                r = cl.plain(prompt_batch(300, 50000 + w * 1000 + i), 150, cache=True)
            except Exception:
                with lock: stats["errors"] += 1
                continue
            with lock:
                stats["req"] += 1; stats["prompt"] += r["prompt_tokens"]; stats["completion"] += r["completion_tokens"]; stats["lat"] += r["wall"]
            i += 1
    ths = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(a.users)]
    for t in ths: t.start()
    time.sleep(5)
    with lock: base = dict(stats)
    t_start = time.time()
    for t in ths: t.join()
    el = time.time() - t_start
    with lock: s = {k: stats[k] - base[k] for k in ("req", "prompt", "completion", "lat")}
    res["multi_user"] = {"users": a.users, "seconds": round(el, 1), "requests": s["req"], "req_per_s": round(s["req"] / el, 2),
                         "prompt_tok_s": round(s["prompt"] / el, 1), "completion_tok_s": round(s["completion"] / el, 1),
                         "total_tok_s": round((s["prompt"] + s["completion"]) / el, 1),
                         "mean_latency_s": round(s["lat"] / s["req"], 2) if s["req"] else None, "errors": stats["errors"]}
    if a.canary:
        here = os.path.dirname(os.path.abspath(__file__)); can = os.path.join(here, "..", "scripts", "gemma4-text-canary.py")
        tmp = a.out + ".canary.json"
        subprocess.run([sys.executable, can, "--base-url", a.base, "--model", a.model, "--repeats", "4", "--out", tmp],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
        try:
            rows = json.load(open(tmp))["rows"]; res["canary"] = {"rows": len(rows), "ok": sum(1 for r in rows if r.get("ok"))}
        except Exception as e:
            res["canary"] = {"error": str(e)}
    res["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("label", "decode_1user", "prefill", "repeat_identical", "batch_identical", "decode_nusers", "multi_user", "canary") if k in res}, indent=None)[:1500])

if __name__ == "__main__":
    main()
