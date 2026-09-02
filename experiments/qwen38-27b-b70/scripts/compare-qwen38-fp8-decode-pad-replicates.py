#!/usr/bin/env python3
"""Multi-replicate comparison for the R118 decode-padding screen.

Reads every ``<arm>-measured.json`` in the run directory whose arm name starts
with ``control`` or ``candidate`` (control, control2, candidate, control3, ...),
reports per-replicate medians, group medians, the noise floor within the control
group, whether every candidate replicate beats every control replicate, and
whether candidate and control c1 token streams agree.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


def load(path: Path) -> dict:
    d = json.loads(path.read_text())
    c1_wall = [b["aggregate_tok_s_wall"] for b in d["batches"] if b["concurrency"] == 1]
    c2_wall = [b["aggregate_tok_s_wall"] for b in d["batches"] if b["concurrency"] == 2]
    c1_after = [r["tok_s_after_ttft_full"] for b in d["batches"] if b["concurrency"] == 1 for r in b["rows"]]
    streams: dict[str, list[int]] = {}
    repeat_identical = True
    for b in d["batches"]:
        if b["concurrency"] == 1:
            for r in b["rows"]:
                prev = streams.setdefault(r["prompt_id"], r["token_ids"])
                repeat_identical = repeat_identical and prev == r["token_ids"]
    return {
        "c1_wall_median": statistics.median(c1_wall), "c1_wall_min": min(c1_wall), "c1_wall_max": max(c1_wall),
        "c1_after_ttft_median": statistics.median(c1_after),
        "c2_wall_median": statistics.median(c2_wall) if c2_wall else None,
        "c1_repeat_identical": repeat_identical,
        "cached_tokens_all_zero": (d.get("oracle") or {}).get("cached_tokens_all_zero"),
        "_streams": streams,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    runs = {}
    for p in sorted(args.run_dir.glob("*-measured.json")):
        arm = p.name[: -len("-measured.json")]
        if re.match(r"^(control|candidate|candidateb)\d*$", arm):
            runs[arm] = load(p)
    groups = {"control": [a for a in runs if a.startswith("control")], "candidate": [a for a in runs if a.startswith("candidate") and not a.startswith("candidateb")], "candidateb": [a for a in runs if a.startswith("candidateb")]}
    report = {"schema": "neural.download.qwen38-fp8-decode-pad-replicates.v1", "order_of_runs": sorted(runs, key=lambda a: Path(args.run_dir / f"{a}-start-time.txt").read_text().strip() if (args.run_dir / f"{a}-start-time.txt").exists() else a),
              "replicates": {a: {k: v for k, v in r.items() if k != "_streams"} for a, r in runs.items()}}
    for metric in ("c1_wall_median", "c1_after_ttft_median", "c2_wall_median"):
        g = {}
        for name, arms in groups.items():
            vals = [runs[a][metric] for a in arms if runs[a][metric] is not None]
            g[name] = {"values": vals, "median": statistics.median(vals) if vals else None, "min": min(vals) if vals else None, "max": max(vals) if vals else None}
        ctrl = g["control"]
        g["control_noise_pct_max_minus_min"] = (ctrl["max"] / ctrl["min"] - 1) * 100 if ctrl["min"] else None
        for cname in ("candidate", "candidateb"):
            cand = g[cname]
            g[f"{cname}_vs_control_median_pct"] = (cand["median"] / ctrl["median"] - 1) * 100 if ctrl["median"] and cand["median"] else None
            g[f"every_{cname}_above_every_control"] = bool(cand["values"] and ctrl["values"] and min(cand["values"]) > max(ctrl["values"]))
            g[f"every_{cname}_below_every_control"] = bool(cand["values"] and ctrl["values"] and max(cand["values"]) < min(ctrl["values"]))
        report[metric] = g
    # token stream agreement
    ref_arm = groups["control"][0] if groups["control"] else None
    agreement = {}
    if ref_arm:
        ref = runs[ref_arm]["_streams"]
        for a, r in runs.items():
            agreement[a] = {pid: (r["_streams"].get(pid) == ref.get(pid)) for pid in ref}
    report["c1_streams_identical_to_first_control"] = agreement
    args.out.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
