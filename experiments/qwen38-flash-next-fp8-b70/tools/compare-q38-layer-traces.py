#!/usr/bin/env python3
"""Compare two Q38 repeatability layer traces record by record.

The reference is a single-row decode capture (MTP0) at position P; the
candidate is a capture whose rows include position P (an MTP verification
batch). For every record label present in both, the candidate row whose
position equals P (from `model_positions`) is compared against the
reference's whole-tensor digest (single row) using the candidate's per-row
digests; the first label that differs is reported per rank file.

    compare-q38-layer-traces.py --reference <rank0.json> --candidate <rank0.json> [--position 2059]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--position", type=int, default=2059)
    args = ap.parse_args()
    ref, cand = load(args.reference), load(args.candidate)
    ref_by = {r["label"]: r["tensors"] for r in ref["records"]}
    cand_by = {r["label"]: r["tensors"] for r in cand["records"]}
    # Which candidate row is the position of interest?
    cpos = cand_by["model_positions"]["positions"]
    ref_pos = ref_by["model_positions"]["positions"]
    cand_rows = cpos.get("head", [])
    row = None
    for i, v in enumerate(cand_rows[: cpos.get("numel", 0)]):
        if int(v) == args.position:
            row = i
    out = {
        "reference_positions": ref_pos.get("head"), "candidate_positions": cand_rows,
        "candidate_row_for_position": row, "position": args.position, "labels": [], "first_difference": None,
    }
    for rec in ref["records"]:
        label = rec["label"]
        if label == "model_positions" or label not in cand_by:
            continue
        for name, rt in rec["tensors"].items():
            ct = cand_by[label].get(name)
            if rt is None or ct is None:
                continue
            if row is not None and "row_sha256" in ct:
                same = ct["row_sha256"][row] == rt["sha256"] if rt.get("shape", [None])[0] == 1 else None
                if same is None:
                    # reference has more than one row too: compare corresponding rows
                    same = ct["row_sha256"][row] == rt.get("row_sha256", [None])[0]
            elif ct.get("shape") == rt.get("shape"):
                same = ct["sha256"] == rt["sha256"]
            else:
                same = None  # different shapes without per-row digests: not comparable
            out["labels"].append({"label": label, "tensor": name, "same": same, "ref_shape": rt["shape"], "cand_shape": ct["shape"]})
            if same is False and out["first_difference"] is None:
                rh = ct.get("row_head")
                cand_head = rh[row][:4] if (rh and row is not None and row < len(rh)) else ct["head"][:4]
                out["first_difference"] = {"label": label, "tensor": name, "ref_head": rt["head"][:4], "cand_row_head": cand_head}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
