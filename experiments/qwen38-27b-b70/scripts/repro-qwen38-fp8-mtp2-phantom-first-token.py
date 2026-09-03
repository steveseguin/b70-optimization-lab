#!/usr/bin/env python3
"""R167: reproduce the depth-2 phantom first token. On the mtp1 (depth-2) server: run the ladder
harness' sequential 64-prompt oracle pass (concurrency 1) exactly as R165 did and list rows whose
first output token is the prompt's last token (id 60) or that differ from the MTP0 oracle. On the mtp0
server: greedy-decode cache-c032 with an extra trailing ']' to test whether the phantom token was in
the model context (identical continuation) or only in the output stream."""
import argparse, json, subprocess, sys, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
repo = "/home/steve/b70-optimization-lab"; suite = f"{repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json"
m0 = {r["prompt_id"]: r["token_ids"] for r in json.load(open("/mnt/fast-ai/bench-results/qwen38-fp8-gdn-split-mixed-full-20260903-r156f/ladder-mtp0/ladder.json"))["oracle"]["rows"]}
if "mtp0" not in a.model:
    lad = a.out.replace("query.json", "ladder-c1.json")
    cmd = [sys.executable, f"{repo}/scripts/bench-openai-concurrency-oracle.py", "--base-url", a.base_url, "--model", a.model, "--api-mode", "completions",
           "--suite", suite, "--concurrency", "64", "--repeats", "1", "--max-tokens", "128", "--seed", "42", "--timeout", "600",
           "--request-extra-json", '{"ignore_eos":true,"temperature":0}', "--return-token-ids", "--require-output-identity", "--out", lad]
    rc = subprocess.run(cmd, capture_output=True, text=True); print("harness exit", rc.returncode)
    d = json.load(open(lad)); rows = d["oracle"]["rows"]
    phantom = [(i, r["prompt_id"], r["token_ids"][:3]) for i, r in enumerate(rows) if r["token_ids"][0] == 60]
    diff = [(i, r["prompt_id"]) for i, r in enumerate(rows) if m0.get(r["prompt_id"]) != r["token_ids"]]
    res = {"kind": "mtp2-sequential-oracle-pass", "phantom_first_token_rows": phantom, "rows_differing_from_mtp0_oracle": diff, "n_rows": len(rows)}
else:
    s = json.load(open(suite))["prompts"]; base = next(x for x in s if x["id"] == "cache")
    prompt = base["prompt"] + "\n\n[Independent validation case 032; variant 04]" + "]"
    body = {"model": a.model, "prompt": prompt, "max_tokens": 127, "temperature": 0, "ignore_eos": True, "seed": 42, "return_token_ids": True}
    req = urllib.request.Request(a.base_url + "/v1/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=300)); ch = resp["choices"][0]
    ids = ch.get("token_ids") or resp.get("token_ids") or []
    ref = m0["cache-c032"]
    res = {"kind": "mtp0-prompt-plus-bracket", "token_ids_head": ids[:8], "equals_mtp0_oracle_tail": ids[:len(ref)] == ref[:len(ids)] if ids else None, "text_head": ch["text"][:80], "n_ids": len(ids)}
json.dump(res, open(a.out, "w"), indent=2); print(json.dumps(res))
