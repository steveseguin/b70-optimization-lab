#!/usr/bin/env python3
"""R209: within-server determinism on the strict suite: each of the 12 prompts sent three times (greedy, seed 42,
256 tokens, ignore_eos) to ONE server; report per-prompt identity across the three repeats and the first divergence."""
import argparse, json, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
suite = json.load(open("/home/steve/b70-optimization-lab/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"))
prompts = suite["prompts"] if isinstance(suite, dict) else suite
def gen(prompt):
    body = {"model": a.model, "prompt": prompt, "max_tokens": 256, "temperature": 0, "seed": 42, "ignore_eos": True, "return_token_ids": True}
    req = urllib.request.Request(a.base_url + "/v1/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600)); ch = r["choices"][0]; return ch.get("token_ids") or r.get("token_ids") or []
res = {"kind": "within-server-repeat", "rows": []}
for p in prompts:
    pid = p.get("id") or p.get("prompt_id"); text = p.get("prompt") or p.get("text")
    runs = [gen(text) for _ in range(3)]
    ident = runs[0] == runs[1] == runs[2]
    div = None
    if not ident:
        for x in runs[1:]:
            if x != runs[0]:
                div = next((i for i in range(min(len(x), len(runs[0]))) if x[i] != runs[0][i]), min(len(x), len(runs[0]))); break
    res["rows"].append({"prompt_id": pid, "identical_x3": ident, "first_divergence": div, "lens": [len(x) for x in runs]})
    print(pid, "identical" if ident else f"DIVERGE@{div}", flush=True)
res["identical_prompts"] = sum(1 for r in res["rows"] if r["identical_x3"]); res["total"] = len(res["rows"])
json.dump(res, open(a.out, "w"), indent=1); print(json.dumps({"identical": res["identical_prompts"], "total": res["total"]}))
