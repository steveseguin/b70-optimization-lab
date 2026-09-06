#!/usr/bin/env python3
"""Print a two-pass concurrency ladder (bench-openai-concurrency-oracle.py output with --repeats N) per rung and repeat:
aggregate tok/s, oracle exactness, max TTFT. usage: summarize-int4-ladders-repeats.py <root> [<root> ...]"""
import json, sys, os
for root in sys.argv[1:]:
    for name in ("ladder", "ladder-mtp0"):
        p = os.path.join(root, name, "ladder.json")
        if not os.path.exists(p): continue
        d = json.load(open(p)); print(f"== {os.path.basename(root)} / {name}")
        for b in d["batches"]:
            rows = b.get("results") or b.get("requests") or b.get("rows") or []
            ttft = max((r.get("ttft_s", 0) for r in rows), default=0)
            print(f"  c{b['concurrency']:3d} r{b.get('repeat',1)}  {b['aggregate_tok_s_wall']:7.1f} tok/s  exact {b['oracle_exact_count']}/{b['oracle_exact_total']}  wall {b['elapsed_s']:6.2f}s  ttft_max {ttft:5.2f}s")
