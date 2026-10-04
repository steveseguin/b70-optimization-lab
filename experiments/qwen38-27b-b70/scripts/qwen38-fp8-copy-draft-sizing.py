"""Offline sizing of copy-from-context drafting (prompt lookup) for the single-user FP8 lane. CPU only.

Replays saved greedy answers: at each step, if the last N tokens of the context occurred earlier, propose the K tokens
that followed that occurrence; count how many the saved answer accepts. A step with a copy draft costs one verify pass
(29.5 ms measured); other steps cost a normal MTP step (33 ms, at the measured tokens per step). It is a model, not a
measurement. Usage: python3 qwen38-fp8-copy-draft-sizing.py /path/to/model (needs the tokenizer and the 2026-10-04 runs).
"""
import json, sys
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(sys.argv[1])
VERIFY, DRAFT = 29.5, 3.5
def lookup(ctx, k, min_n, max_n=8):
    L = len(ctx)
    for n in range(min(max_n, L - 1), min_n - 1, -1):
        suf = ctx[L - n:]
        for start in range(L - n - 1, -1, -1):
            if ctx[start:start + n] == suf:
                prop = ctx[start + n:start + n + k]
                if prop: return prop
    return []
def run(pairs, k, min_n, mtp_tps):
    """mtp_tps: tokens per MTP step for each request (measured where known, else 2.978)."""
    tot = 0; t_mtp = 0.0; t_hyb = 0.0; hist = {}
    for (prompt_ids, out_ids), tps in zip(pairs, mtp_tps):
        T = len(out_ids); tot += T; t_mtp += T / tps * (VERIFY + DRAFT)
        ctx = list(prompt_ids); i = 0
        while i < T:
            prop = lookup(ctx, k, min_n)
            if prop:
                acc = 0
                while acc < len(prop) and i + acc < T and prop[acc] == out_ids[i + acc]: acc += 1
                emit = min(acc + 1, T - i); t_hyb += VERIFY; hist[acc] = hist.get(acc, 0) + 1
            else:
                emit = min(max(1, round(tps)), T - i); t_hyb += (VERIFY + DRAFT) * emit / tps
            ctx += out_ids[i:i + emit]; i += emit
        n = sum(hist.values())
    return tot, t_mtp, t_hyb, hist
def show(name, pairs, mtp_tps):
    print(f"{name}: {len(pairs)} requests, {sum(len(o) for _, o in pairs)} answer tokens, measured MTP tokens/step {sum(len(o) for _,o in pairs)/sum(len(o)/t for (_,o),t in zip(pairs,mtp_tps)):.2f}")
    for k in (5, 8, 16):
        for min_n in (3, 4, 6):
            tot, t_mtp, t_hyb, hist = run(pairs, k, min_n, mtp_tps)
            n = sum(hist.values()); mean = sum(a * c for a, c in hist.items()) / max(1, n)
            print(f"   draft {k:2d} tokens, match >= {min_n}: copy drafts on {n:4d} steps, mean accepted {mean:.2f}, wasted (0 accepted) {hist.get(0,0):3d} -> model {(t_mtp/t_hyb-1)*100:+6.1f}%")
# long prompts (speculation-off run: no measured MTP rate, use the lane average 2.978)
suite = {p["id"]: p["prompt"] for p in json.load(open("experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json"))["prompts"]}
rows = json.load(open("/mnt/fast-ai/bench-results/fp8-multiuser-three-s64-20261004/tp2-pure-faseq-head4-mtp0-s64-long-concurrency.json"))["oracle"]["rows"][:8]
pairs = [(tok(suite[r["prompt_id"].rsplit("-c", 1)[0]], add_special_tokens=False)["input_ids"], r["token_ids"]) for r in rows]
show("long prompts (2K-8K), 128-token answers", pairs, [2.978] * len(pairs))
suite = {p["id"]: p["prompt"] for p in json.load(open("experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json"))["prompts"]}
rows = json.load(open("/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-ladder.json"))["oracle"]["rows"]
pairs = [(tok(suite.get(r["prompt_id"], suite.get(r["prompt_id"].rsplit("-c", 1)[0], "")), add_special_tokens=False)["input_ids"], r["token_ids"]) for r in rows]
show("short ladder (31-token prompts), 128-token answers", pairs, [2.978] * len(pairs))
rows = json.load(open("/mnt/fast-ai/bench-results/fp8-tp2-acceptance-chunked-20261004/strict/performance.json"))["rows"]
pairs = [([], r["token_ids"]) for r in rows]
show("published strict suite (12 prompts, 512-token answers; prompt text not used)", pairs, [len(r["token_ids"]) / r["chunk_count"] for r in rows])
