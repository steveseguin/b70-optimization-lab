#!/usr/bin/env python3
"""Compare the R118 control (pad 0) and candidate (pad 32) arms.

Screening only: same image, same boot, servers run back to back. Reports the
median c1 and c2 aggregate wall tok/s per arm from the concurrency-oracle
harness, the relative change, whether each arm's own c1 outputs were
repeat-identical, and where (if anywhere) candidate c1 streams diverge from
control c1 streams for the same prompt.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def load_rows(path: Path):
    d = json.loads(path.read_text())
    by_conc: dict[int, list[float]] = {}
    after_ttft: dict[int, list[float]] = {}
    streams: dict[str, set[str]] = {}
    ids_by_prompt: dict[str, list[int]] = {}
    for b in d["batches"]:
        by_conc.setdefault(b["concurrency"], []).append(float(b["aggregate_tok_s_wall"]))
        for row in b["rows"]:
            if row.get("tok_s_after_ttft_full") is not None:
                after_ttft.setdefault(b["concurrency"], []).append(float(row["tok_s_after_ttft_full"]))
        if b["concurrency"] == 1:
            for row in b["rows"]:
                ids = row.get("token_ids") or []
                streams.setdefault(row["prompt_id"], set()).add(json.dumps(ids))
                ids_by_prompt.setdefault(row["prompt_id"], ids)
    load_rows.after_ttft = after_ttft
    oracle_rows = {r["prompt_id"]: (r.get("token_ids") or []) for r in d.get("oracle", {}).get("rows", [])}
    return by_conc, streams, ids_by_prompt, oracle_rows, d


def first_div(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    arms = {}
    for arm in ("control", "candidate"):
        p = args.run_dir / f"{arm}-measured.json"
        if not p.exists():
            arms[arm] = {"missing": True}
            continue
        by_conc, streams, ids, oracle, d = load_rows(p)
        after = load_rows.after_ttft
        arms[arm] = {
            "c1_per_request_tok_s_after_ttft": sorted(after.get(1, [])),
            "c1_median_tok_s_after_ttft": statistics.median(after[1]) if after.get(1) else None,
            "c2_median_per_request_tok_s_after_ttft": statistics.median(after[2]) if after.get(2) else None,
            "c1_tok_s": sorted(by_conc.get(1, [])),
            "c1_median_tok_s": statistics.median(by_conc[1]) if by_conc.get(1) else None,
            "c2_tok_s": sorted(by_conc.get(2, [])),
            "c2_median_tok_s": statistics.median(by_conc[2]) if by_conc.get(2) else None,
            "c1_repeat_identical_per_prompt": {k: len(v) == 1 for k, v in streams.items()},
            "own_oracle_exact_all": (d.get("identity_qualification") or {}).get("complete_outputs_exact_vs_sequential_oracle"),
            "cached_tokens_all_zero": d.get("oracle", {}).get("cached_tokens_all_zero"),
            "_ids": ids,
        }
    report = {"schema": "neural.download.qwen38-fp8-decode-pad-arms-comparison.v1", "arms": {}}
    for arm, a in arms.items():
        report["arms"][arm] = {k: v for k, v in a.items() if k != "_ids"}
    if all("_ids" in arms[a] for a in ("control", "candidate")):
        c, k = arms["control"], arms["candidate"]
        report["c1_median_change_pct"] = (k["c1_median_tok_s"] / c["c1_median_tok_s"] - 1) * 100 if c["c1_median_tok_s"] else None
        report["c2_median_change_pct"] = (k["c2_median_tok_s"] / c["c2_median_tok_s"] - 1) * 100 if c["c2_median_tok_s"] else None
        report["c1_after_ttft_median_change_pct"] = (k["c1_median_tok_s_after_ttft"] / c["c1_median_tok_s_after_ttft"] - 1) * 100 if c.get("c1_median_tok_s_after_ttft") else None
        report["candidate_vs_control_c1_streams"] = {
            pid: {"identical": c["_ids"].get(pid) == k["_ids"].get(pid), "first_divergence": first_div(c["_ids"].get(pid, []), k["_ids"].get(pid, []))}
            for pid in sorted(set(c["_ids"]) | set(k["_ids"]))
        }
    args.out.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
