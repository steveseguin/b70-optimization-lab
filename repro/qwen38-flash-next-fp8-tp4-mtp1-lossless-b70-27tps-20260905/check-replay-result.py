#!/usr/bin/env python3
"""Compare a replay's realistic-suite-v1-result.json with the A189 record.

Pass: every prompt and output SHA-256 equals the record's (bit-identical text),
every fresh-response and final-gate boolean equals the record's value, and the class-balanced median
is printed next to the record's 27.048435 tok/s. Speed is reported, not gated:
a slower replay with identical outputs is still an exact replay.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORD = HERE.parents[1] / "experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp1-a189-realistic-suite-v1-result.json"


def gates(rep, rec):
    """Every boolean gate must equal the record's value (some are meant to be false,
    e.g. prefix reuse, history acceleration, ignore_eos)."""
    bad = []
    for section in ("fresh_response_validity", "realistic_final_gate"):
        for k, v in rec[section].items():
            if isinstance(v, bool) and rep[section].get(k) != v:
                bad.append(f"{section}.{k}={rep[section].get(k)!r} (record {v!r})")
    return bad


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rec = json.load(open(RECORD)); rep = json.load(open(sys.argv[1]))
    ok = True
    if rep["prompt_sha256s"] != rec["prompt_sha256s"]:
        print("FAIL: prompt set differs from the record"); ok = False
    if rep["output_sha256s"] != rec["output_sha256s"]:
        diff = sum(a != b for a, b in zip(rep["output_sha256s"], rec["output_sha256s"]))
        print(f"FAIL: {diff} of {len(rec['output_sha256s'])} outputs differ from the record"); ok = False
    bad = gates(rep, rec)
    if bad:
        print("FAIL: gates differ from the record:", ", ".join(bad)); ok = False
    med = rep["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    print(f"replay class-balanced median: {med:.6f} tok/s (record 27.048435)")
    print("PASS: bit-identical outputs and all gates hold" if ok else "replay is NOT an exact replay")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
