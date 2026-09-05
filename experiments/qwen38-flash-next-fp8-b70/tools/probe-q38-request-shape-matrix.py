#!/usr/bin/env python3
"""Request-shape matrix: the same prompt through different OpenAI request shapes,
per-chunk arrival timing, to attribute the gap between the completions short bench
and the chat realistic suite on one running server."""
from __future__ import annotations
import argparse, hashlib, json, statistics, time, urllib.request

CELLS = {
    "suite": dict(api="chat", seed=True, top_p=True, ids=True, usage=True),
    "chat-noids": dict(api="chat", seed=True, top_p=True, ids=False, usage=True),
    "chat-plain": dict(api="chat", seed=False, top_p=False, ids=False, usage=True),
    "chat-plain-nousage": dict(api="chat", seed=False, top_p=False, ids=False, usage=False),
    "completions-raw": dict(api="completions", seed=True, top_p=False, ids=False, usage=True),
    "completions-ignore-eos": dict(api="completions", seed=True, top_p=False, ids=False, usage=True, ignore_eos=True),
    "completions-ids": dict(api="completions", seed=True, top_p=False, ids=True, usage=True),
}

def build(cell, prompt, model, max_tokens, seed):
    c = CELLS[cell]
    p = {"model": model, "max_tokens": max_tokens, "temperature": 0, "stream": True}
    if c["usage"]: p["stream_options"] = {"include_usage": True}
    if c["seed"]: p["seed"] = seed
    if c["top_p"]: p["top_p"] = 1
    if c["ids"]: p["return_token_ids"] = True
    if c.get("ignore_eos"): p["ignore_eos"] = True
    if c["api"] == "chat":
        p["messages"] = [{"role": "user", "content": prompt}]
        p["chat_template_kwargs"] = {"enable_thinking": False}
        url = "/v1/chat/completions"
    else:
        p["prompt"] = prompt
        url = "/v1/completions"
    return url, p

def run(base, url, payload, timeout):
    req = urllib.request.Request(base + url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); chunks = []; text = []; usage = None; first = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:"): continue
            body = line[5:].strip()
            if body == "[DONE]": break
            d = json.loads(body); now = time.perf_counter() - t0
            if d.get("usage"): usage = d["usage"]
            for ch in d.get("choices", []):
                delta = ch.get("delta") or {}
                piece = delta.get("content") if "delta" in ch else ch.get("text")
                ids = delta.get("token_ids") or ch.get("token_ids") or []
                if piece is None and not ids: continue
                if first is None: first = now
                chunks.append((now, len(ids) if ids else None)); text.append(piece or "")
    return dict(ttft_s=first, chunks=chunks, text="".join(text), usage=usage, total_s=time.perf_counter() - t0)

def summarize(r, metric_tokens):
    ts = [c[0] for c in r["chunks"]]; iv = [b - a for a, b in zip(ts, ts[1:])]
    comp = (r["usage"] or {}).get("completion_tokens")
    ids_known = all(c[1] is not None for c in r["chunks"]) and r["chunks"]
    tokens = sum(c[1] for c in r["chunks"]) if ids_known else comp
    med = lambda xs: round(statistics.median(xs) * 1000, 1) if xs else None
    out = dict(ttft_s=round(r["ttft_s"], 3) if r["ttft_s"] else None, chunk_count=len(ts), completion_tokens=comp,
               tokens=tokens, tok_per_chunk=round(tokens / len(ts), 3) if tokens and ts else None,
               interval_ms_first50=med(iv[:50]), interval_ms_mid50=med(iv[len(iv)//2-25:len(iv)//2+25]), interval_ms_last50=med(iv[-50:]),
               interval_ms_max=round(max(iv) * 1000, 1) if iv else None,
               tok_s_post_ttft=round((tokens - 1) / (ts[-1] - ts[0]), 3) if tokens and len(ts) > 1 else None,
               text_sha256=hashlib.sha256(r["text"].encode()).hexdigest(), total_s=round(r["total_s"], 2))
    if ids_known:
        offs = []
        for t, n in r["chunks"]: offs.extend([t] * n)
        if len(offs) >= metric_tokens:
            out["tok_s_1_%d_intervals_after_ttft" % metric_tokens] = round((metric_tokens - 1) / (offs[metric_tokens-1] - offs[0]), 3)
    elif tokens and len(ts) > 1:
        per = tokens / len(ts); k = max(2, int(round(metric_tokens / per)))
        k = min(k, len(ts))
        out["tok_s_1_%d_chunk_estimate" % metric_tokens] = round((k - 1) * per / (ts[k-1] - ts[0]), 3)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--suite", required=True); ap.add_argument("--prompt-ids", required=True)
    ap.add_argument("--cells", default=",".join(CELLS)); ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--metric-tokens", type=int, default=100); ap.add_argument("--seed", type=int, default=20260609)
    ap.add_argument("--warmup-tokens", type=int, default=64); ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    suite = json.load(open(a.suite)); prompts = {p["id"]: p["prompt"] for p in suite["prompts"]}
    ids = a.prompt_ids.split(","); cells = a.cells.split(",")
    results = []
    url, p = build("chat-plain", prompts[ids[-1]], a.model, a.warmup_tokens, a.seed)
    w = run(a.base_url, url, p, a.timeout); results.append(dict(cell="warmup", prompt_id=ids[-1], **summarize(w, a.metric_tokens)))
    print("warmup", json.dumps(results[-1]), flush=True)
    order = [(c, pid) for pid in ids for c in cells] + [(cells[0], ids[0])]
    for cell, pid in order:
        url, p = build(cell, prompts[pid], a.model, a.max_tokens, a.seed)
        r = run(a.base_url, url, p, a.timeout)
        results.append(dict(cell=cell, prompt_id=pid, request=p if cell == cells[0] else None, **summarize(r, a.metric_tokens)))
        print(cell, pid, json.dumps({k: v for k, v in results[-1].items() if k not in ("request",)}), flush=True)
    json.dump(dict(cells=CELLS, model=a.model, base_url=a.base_url, max_tokens=a.max_tokens, seed=a.seed, results=results), open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
