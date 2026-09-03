#!/usr/bin/env python3
"""Greedy-decode one ladder-suite prompt with top logprobs, so a first-token difference between
two profiles can be read as a tie, a flip, or a phantom token. Completions API, temperature 0."""
import argparse, json, urllib.request
ap = argparse.ArgumentParser()
ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--suite", default="/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json")
ap.add_argument("--prompt-id", default="cache-c032"); ap.add_argument("--max-tokens", type=int, default=8)
a = ap.parse_args()
suite = json.load(open(a.suite))["prompts"]
import re
m = re.fullmatch(r"(.+)-c(\d+)", a.prompt_id); base_id, index = m.group(1), int(m.group(2))
base = next(x for x in suite if x["id"] == base_id)
variant = index // len(suite)
prompt = base["prompt"] + f"\n\n[Independent validation case {index:03d}; variant {variant:02d}]"  # as scripts/bench-openai-concurrency-oracle.py expand_prompts
body = {"model": a.model, "prompt": prompt, "max_tokens": a.max_tokens, "temperature": 0, "logprobs": 5, "ignore_eos": True, "seed": 42}
req = urllib.request.Request(a.base_url + "/v1/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
resp = json.load(urllib.request.urlopen(req, timeout=300))
ch = resp["choices"][0]; lp = ch["logprobs"]
out = {"prompt_id": a.prompt_id, "prompt_tail": prompt[-120:] if isinstance(prompt, str) else prompt, "text": ch["text"], "tokens": lp["tokens"], "token_logprobs": lp["token_logprobs"], "top_logprobs": lp["top_logprobs"], "usage": resp.get("usage")}
json.dump(out, open(a.out, "w"), indent=2)
print(" | ".join(f"{i}:{t!r}={l:.4f} top={sorted(tp.items(), key=lambda kv: -kv[1])[:2]}" for i, (t, l, tp) in enumerate(zip(lp["tokens"], lp["token_logprobs"], lp["top_logprobs"]))))
