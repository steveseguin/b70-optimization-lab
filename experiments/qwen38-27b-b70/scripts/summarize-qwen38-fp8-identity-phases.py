#!/usr/bin/env python3
"""Summarize phased concurrency-oracle runs: per-batch exactness, first divergence,
scheduler shape from the GDN projection trace, and selector markers from the log."""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path


def first_divergence(observed: list[int], oracle: list[int]) -> dict | None:
    for i, (a, b) in enumerate(zip(observed, oracle)):
        if a != b:
            return {"zero_based_index": i, "observed": a, "oracle": b}
    if len(observed) != len(oracle):
        return {"zero_based_index": min(len(observed), len(oracle)), "observed": None, "oracle": None}
    return None


def token_ids_sha256(token_ids: list[int]) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(token_ids, separators=(",", ":")).encode()).hexdigest()


REFERENCE: dict[str, list[int]] = {}


def summarize_file(path: Path) -> dict:
    d = json.loads(path.read_text())
    oracle_rows = {r["prompt_id"]: r for r in d.get("oracle", {}).get("rows", [])}
    # The pinned oracle stores digests only; recover full reference streams from
    # any row in this run whose complete token IDs reproduce the oracle digest.
    for b in d.get("batches", []):
        for row in b.get("rows", []):
            ids = row.get("token_ids") or []
            oracle = oracle_rows.get(row["prompt_id"], {})
            if ids and oracle.get("token_ids_sha256") and token_ids_sha256(ids) == oracle["token_ids_sha256"]:
                REFERENCE.setdefault(row["prompt_id"], ids)
    batches = []
    for b in d.get("batches", []):
        misses = []
        for row in b.get("rows", []):
            oracle = oracle_rows.get(row["prompt_id"], {})
            ids = row.get("token_ids") or []
            oracle_ids = oracle.get("token_ids")
            if oracle_ids:
                exact = ids == oracle_ids
            elif oracle.get("token_ids_sha256") and ids:
                exact = token_ids_sha256(ids) == oracle["token_ids_sha256"]
            else:
                exact = row.get("sha256") == oracle.get("sha256")
            if not exact:
                ref = oracle_ids or REFERENCE.get(row["prompt_id"])
                misses.append({
                    "prompt_id": row["prompt_id"],
                    "completion_tokens": row.get("completion_tokens"),
                    "cached_tokens": ((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens", row.get("cached_tokens")),
                    "observed_token_ids_sha256": token_ids_sha256(ids) if ids else None,
                    "first_divergence": first_divergence(ids, ref) if ref else None,
                })
        batches.append({
            "concurrency": b.get("concurrency"),
            "repeat": b.get("repeat"),
            "oracle_exact": f"{b.get('oracle_exact_count')}/{b.get('oracle_exact_total')}",
            "aggregate_tok_s": b.get("aggregate_tok_s"),
            "misses": misses,
        })
    exact_batches = sum(1 for b in batches if not b["misses"])
    exact_outputs = sum(int(b["oracle_exact"].split("/")[0]) for b in batches)
    total_outputs = sum(int(b["oracle_exact"].split("/")[1]) for b in batches)
    return {
        "file": path.name,
        "classification": d.get("classification"),
        "cached_tokens_all_zero": d.get("identity_qualification", {}).get("cached_tokens_all_zero", d.get("oracle", {}).get("cached_tokens_all_zero")),
        "exact_batches": f"{exact_batches}/{len(batches)}",
        "exact_outputs": f"{exact_outputs}/{total_outputs}",
        "batches": batches,
    }


def trace_shapes(trace: Path) -> dict:
    if not trace.exists():
        return {"present": False}
    counter = collections.Counter()
    invocations = []
    for line in trace.read_text().splitlines():
        r = json.loads(line)
        if r.get("rank") == 0 and r.get("layer", "").endswith("layers.0.linear_attn"):
            shape = (r.get("num_prefills"), tuple(q.get("row_count") for q in r.get("requests", [])), r.get("treatment"))
            counter[str(shape)] += 1
            invocations.append({"invocation": r.get("invocation"), "num_prefills": r.get("num_prefills"), "row_counts": [q.get("row_count") for q in r.get("requests", [])], "treatment": r.get("treatment")})
    return {"present": True, "layer0_rank0_shape_counts": dict(counter), "layer0_rank0_invocations": invocations}


def markers(server_log: Path) -> dict:
    text = server_log.read_text(errors="replace") if server_log.exists() else ""
    wanted = [
        "R117 Qwen GDN live-metadata single-request R99 arm executed",
        "R117 Qwen GDN live-metadata multi-request R99 arm executed",
        "R101 Qwen GDN metadata-free profile R99 arm executed",
        "R97 arm executed",
        "R116 layer-0 MLP multi-prefill treatment executed",
        "R116 layer-0 MLP multi-request decode-or-mixed treatment executed",
        "R116 layer-0 MLP single-request control executed",
    ]
    return {m: len(re.findall(re.escape(m), text)) for m in wanted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--phases", default="warm-c1,warm-c2,staggered-c2,counted-c1,counted-c2")
    parser.add_argument("--trace-name", default="gdn-projection-trace-r117.jsonl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema": "neural.download.qwen38-fp8-identity-phase-summary.v1", "phases": {}}
    for phase in args.phases.split(","):
        p = args.run_dir / f"{phase}.json"
        report["phases"][phase] = summarize_file(p) if p.exists() else {"missing": True}
    report["trace"] = trace_shapes(args.run_dir / "cache" / args.trace_name)
    report["server_markers"] = markers(args.run_dir / "server.log")
    args.out.write_text(json.dumps(report, indent=1))
    for phase, s in report["phases"].items():
        if "missing" in s:
            print(f"{phase}: missing")
            continue
        print(f"{phase}: batches {s['exact_batches']} outputs {s['exact_outputs']} cache_zero={s['cached_tokens_all_zero']}")
        for b in s["batches"]:
            for m in b["misses"]:
                print(f"   miss c{b['concurrency']} r{b['repeat']} {m['prompt_id']} first_div={m['first_divergence']}")
    print("markers:", json.dumps(report["server_markers"]))
    print("layer0 shapes:", json.dumps(report["trace"].get("layer0_rank0_shape_counts")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
