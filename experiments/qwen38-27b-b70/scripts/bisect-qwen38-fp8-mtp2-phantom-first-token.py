#!/usr/bin/env python3
"""R168: bisect the depth-2 phantom first token on one ladder-config server.
Phase A: 33 sequential requests of the SAME prompt (cache-c032) -> is the phantom positional (33rd request) or prompt+history bound?
Phase B: the 64 harness prompts in rotated order (start at index 1) -> does it land on cache-c032 again or on the 33rd request again?
Every request is the harness' own post_stream (completions, stream, ignore_eos, temperature 0, seed 42, 128 tokens)."""
import argparse, importlib.util, json
ap = argparse.ArgumentParser(); ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
repo = "/home/steve/b70-optimization-lab"
spec = importlib.util.spec_from_file_location("base", f"{repo}/scripts/bench-openai-realistic-suite.py"); base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
suite = json.load(open(f"{repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json"))["prompts"]
def expand(i):
    b = suite[i % len(suite)]; return {"id": f"{b['id']}-c{i:03d}", "prompt": b["prompt"] + f"\n\n[Independent validation case {i:03d}; variant {i // len(suite):02d}]"}
m0 = {r["prompt_id"]: r["token_ids"] for r in json.load(open("/mnt/fast-ai/bench-results/qwen38-fp8-gdn-split-mixed-full-20260903-r156f/ladder-mtp0/ladder.json"))["oracle"]["rows"]}
n = 0
def run(item, tag):
    global n
    r = base.post_stream(base_url=a.base_url, model=a.model, prompt=item["prompt"], max_tokens=128, timeout=600, api_mode="completions", seed=42,
                         request_extra={"ignore_eos": True, "temperature": 0}, return_token_ids=True, system_prompt=None, request_id=f"bisect-{tag}-{n:03d}")
    ids = r["token_ids"]; n += 1
    return {"seq": n - 1, "tag": tag, "prompt_id": item["id"], "first_ids": ids[:3], "phantom": ids[0] == 60, "equals_mtp0": m0.get(item["id"]) == ids,
            "tail_equals_mtp0_shifted": m0.get(item["id"]) is not None and ids[1:] == m0[item["id"]][:127], "chunk_offsets_head": r.get("chunk_offsets_s", [])[:3]}
log = []
c032 = expand(32)
for k in range(33): log.append(run(c032, "A-same-prompt"))
for k in range(64): log.append(run(expand((k + 1) % 64), "B-rotated"))
json.dump(log, open(a.out, "w"), indent=2)
print("phantoms:", [(x["seq"], x["tag"], x["prompt_id"]) for x in log if x["phantom"]], "| non-identical:", [(x["seq"], x["prompt_id"]) for x in log if not x["equals_mtp0"] and not x["phantom"]])
