#!/usr/bin/env python3
"""Print a table of the profile JSONs in a directory (tools/profile-openai-endpoint.py output)."""
import json, sys, glob, os

d = sys.argv[1] if len(sys.argv) > 1 else "."
rows = []
for f in sorted(glob.glob(os.path.join(d, "*.json"))):
    if f.endswith(".canary.json"): continue
    try: j = json.load(open(f))
    except Exception: continue
    pre = j.get("prefill", {}); mu = j.get("multi_user", {}); nu = j.get("decode_nusers", {}); can = j.get("canary") or {}
    rows.append((j.get("label", os.path.basename(f))[:48],
                 round(j.get("decode_1user", {}).get("median_tps") or 0, 1),
                 (pre.get("512") or {}).get("prompt_tps"), (pre.get("2048") or {}).get("prompt_tps"), (pre.get("8192") or {}).get("prompt_tps"),
                 j.get("users"), nu.get("aggregate_tps"), mu.get("total_tok_s"), mu.get("completion_tok_s"),
                 j.get("repeat_identical", {}).get("distinct"), j.get("batch_identical", {}).get("distinct_incl_alone"),
                 f"{can.get('ok','-')}/{can.get('rows','-')}" if can else "-", j.get("card_memory_used_mib_after_load")))
hdr = ("label", "dec1", "pf512", "pf2k", "pf8k", "N", "decN_agg", "load_total", "load_compl", "rep_distinct", "batch_distinct", "canary", "mem_mib")
w = [48, 6, 7, 7, 7, 3, 9, 10, 10, 12, 14, 8, 8]
print("  ".join(str(h).ljust(x) for h, x in zip(hdr, w)))
for r in rows:
    print("  ".join(str(v if v is not None else "-").ljust(x) for v, x in zip(r, w)))
