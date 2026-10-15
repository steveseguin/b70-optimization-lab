#!/usr/bin/env python3
"""Logprob-level identity probe for a llama.cpp server: the 12 realistic-suite prompts, greedy, N tokens each,
recording every generated token id and the top-8 log-probabilities at each step.

  identity_probe.py run  --base-url URL --out FILE [--tokens 96]
  identity_probe.py diff REF.json CAND.json [more ...]

Any arithmetic difference in the forward pass shows up as a changed log-probability long before it flips a greedy
token, so this is a much finer check than comparing token arrays. `diff` exits 0 only when every candidate matches
REF exactly (token ids and every logged probability value).
"""
import argparse
import json
import sys
import urllib.request

SUITE = "/home/steve/b70-optimization-lab/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"


def post(url, payload, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def run(args):
    suite = json.load(open(args.prompts or SUITE))
    prompts = suite["prompts"]
    out = {"base_url": args.base_url, "tokens": args.tokens, "rows": []}
    for p in prompts:
        rendered = post(f"{args.base_url}/apply-template", {"messages": [{"role": "user", "content": p["prompt"]}]})["prompt"]
        r = post(f"{args.base_url}/completion", {
            "prompt": rendered, "n_predict": args.tokens, "temperature": 0, "top_k": 1, "seed": 42,
            "cache_prompt": False, "n_probs": 8, "post_sampling_probs": False, "return_tokens": True,
        })
        steps = []
        for st in r.get("completion_probabilities", []):
            steps.append([st.get("id"), st.get("logprob"),
                          [[t.get("id"), t.get("logprob")] for t in st.get("top_logprobs", [])]])
        tps = (r.get("timings") or {}).get("predicted_per_second")
        out["rows"].append({"prompt_id": p["id"], "tokens": r.get("tokens"), "steps": steps, "decode_tok_s": tps})
        print(f"{p['id']}: {len(steps)} steps, {tps:.1f} tok/s" if tps else f"{p['id']}: {len(steps)} steps", file=sys.stderr)
    json.dump(out, open(args.out, "w"))


def diff(paths):
    ref = {r["prompt_id"]: r for r in json.load(open(paths[0]))["rows"]}
    ok = True
    for path in paths[1:]:
        cand = {r["prompt_id"]: r for r in json.load(open(path))["rows"]}
        exact, notes, maxdev = 0, [], 0.0
        for pid, r in ref.items():
            c = cand.get(pid)
            if c is None:
                notes.append(f"{pid}:missing")
                continue
            if c["steps"] == r["steps"] and c["tokens"] == r["tokens"]:
                exact += 1
                continue
            first = None
            for i, (a, b) in enumerate(zip(r["steps"], c["steps"])):
                if a != b:
                    first = i if first is None else first
                    if a[0] == b[0] and a[1] is not None and b[1] is not None:
                        maxdev = max(maxdev, abs(a[1] - b[1]))
                    if a[0] != b[0]:
                        notes.append(f"{pid}:token@{i}")
                        break
            else:
                notes.append(f"{pid}:probs@{first}")
        ok &= exact == len(ref)
        speeds = sorted(r["decode_tok_s"] for r in cand.values() if r.get("decode_tok_s"))
        med = f"; median decode {speeds[len(speeds) // 2]:.1f} tok/s (server timing, screening only)" if speeds else ""
        print(f"{path}: {exact}/{len(ref)} bit-exact{med}; max |dlogprob| on agreeing steps {maxdev:.3g}"
              + (f"; {', '.join(notes)}" if notes else ""))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--base-url", default="http://127.0.0.1:18110")
    r.add_argument("--out", required=True)
    r.add_argument("--tokens", type=int, default=96)
    r.add_argument("--prompts", help="JSON file with {'prompts': [{'id', 'prompt'}]} instead of the realistic suite")
    d = sub.add_parser("diff")
    d.add_argument("paths", nargs="+")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)
        return 0
    return diff(a.paths)


if __name__ == "__main__":
    sys.exit(main())
