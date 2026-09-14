#!/usr/bin/env python3
"""CPU-only raw-bit and max-rank paired latency analysis."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

SHAPES = (1, 2, 512, 4096)
KINDS = ("varied", "cancel", "signed_zero", "subnormal", "overflow", "rounding", "nan_inf")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def paired_latency(ranks):
    """For each ABBA occurrence take max(rank0,rank1), then arm/block medians."""
    if len(ranks) != 2 or len(ranks[0]) != 20 or len(ranks[1]) != 20:
        raise ValueError("require two ranks and five four-arm blocks")
    groups = {b: {"xccl": [], "candidate": []} for b in range(5)}
    for index, (a, b) in enumerate(zip(*ranks)):
        block = index // 4
        order = ["xccl", "candidate", "candidate", "xccl"] if block % 2 == 0 else ["candidate", "xccl", "xccl", "candidate"]
        arm = order[index % 4]
        if any(row["block"] != block or row["arm"] != arm for row in (a, b)):
            raise ValueError("rank timing order differs from fixed ABBA/BAAB")
        values = [row["ns_per_call"] for row in (a, b)]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("invalid timing")
        groups[block][arm].append(max(values))
    blocks = []
    for block, arms in groups.items():
        control = statistics.median(arms["xccl"])
        candidate = statistics.median(arms["candidate"])
        blocks.append({"block": block, "xccl_ns": control, "candidate_ns": candidate,
                       "relative_improvement": 1 - candidate / control})
    improvements = [b["relative_improvement"] for b in blocks]
    median = statistics.median(improvements)
    return {"blocks": blocks, "median_relative_improvement": median,
            "positive_blocks": sum(x > 0 for x in improvements),
            "operator_speed_gate": median >= .05 and all(x > 0 for x in improvements),
            "accounting": "max rank latency for each matched arm occurrence, median within arm/block, median of five paired improvements",
            "threshold": "at least 5% paired median improvement and all five blocks positive"}


def analyze(directory):
    result = {"schema": "neural.download.exact-tp2-operator-screen.v1", "shapes": [],
              "runtime_qualified": False, "promoted": False, "errors": []}
    quality = []
    for rank in range(2):
        quality.append(json.loads((directory / f"rank{rank}-quality.json").read_text()))
        if not (directory / f"rank{rank}-DONE.json").is_file():
            result["errors"].append(f"rank{rank} has no completion receipt")
    for rows in SHAPES:
        hashes = []
        try:
            for rank in range(2):
                records = [r for r in quality[rank] if r["rows"] == rows]
                if len(records) != 14 or {(r["kind"], r["repeat"]) for r in records} != {(k, r) for k in KINDS for r in (0, 1)}:
                    raise ValueError("missing or duplicate quality cases")
                by_key = {}
                for record in records:
                    stem = f"rank{rank}-rows{rows}-{record['kind']}-{record['repeat']}"
                    candidate = directory / f"{stem}.candidate.bin"
                    control = directory / f"{stem}.xccl.bin"
                    if candidate.stat().st_size != rows * 5120 * 2 or control.stat().st_size != candidate.stat().st_size:
                        raise ValueError("raw output length mismatch")
                    if not record["exact"] or not record["input_unchanged"]:
                        raise ValueError("operator quality or input-lifetime failure")
                    actual = sha(candidate)
                    if actual != sha(control) or actual != record["candidate_sha256"] or actual != record["xccl_sha256"]:
                        raise ValueError("raw XCCL output or evidence hash mismatch")
                    by_key[(record["kind"], record["repeat"])] = actual
                hashes.append(by_key)
            if hashes[0] != hashes[1]:
                raise ValueError("rank output disagreement")
            ranks = [json.loads((directory / f"rank{rank}-rows{rows}-timing.json").read_text()) for rank in range(2)]
            result["shapes"].append({"rows": rows, "elements": rows * 5120,
                                     "quality_passed": True, **paired_latency(ranks)})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["errors"].append(f"rows{rows}: {type(exc).__name__}: {exc}")
    result["quality_passed"] = not result["errors"] and len(result["shapes"]) == len(SHAPES)
    result["qualified_operator_shapes"] = [s["rows"] for s in result["shapes"] if s["operator_speed_gate"]] if result["quality_passed"] else []
    result["endpoint_integration_admitted"] = bool(result["qualified_operator_shapes"])
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.write_text(json.dumps(analyze(args.directory), indent=2) + "\n")
