#!/usr/bin/env python3
"""Compare the generated token arrays of two realistic-suite runs, prompt by prompt.

  compare_arrays.py REF.json CANDIDATE.json [more candidates ...]

For each candidate prints how many of the prompts produced the identical token array as REF, the first index where
each other one diverges, and the class-balanced speed of both. Exit status 0 only when every candidate is identical
on every prompt.
"""
import json
import sys


def load(path):
    d = json.load(open(path))
    rows = {r["prompt_id"]: r["token_ids"] for r in d["rows"]}
    speed = d["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    return rows, speed


def main():
    ref, ref_speed = load(sys.argv[1])
    ok = True
    for path in sys.argv[2:]:
        cand, speed = load(path)
        same, diffs = 0, []
        for pid, toks in ref.items():
            other = cand.get(pid)
            if other == toks:
                same += 1
                continue
            first = next((i for i, (a, b) in enumerate(zip(toks, other or [])) if a != b), min(len(toks), len(other or [])))
            diffs.append(f"{pid}@{first}")
        ok &= same == len(ref)
        print(f"{path}: {same}/{len(ref)} identical; speed {speed:.2f} vs {ref_speed:.2f} tok/s ({speed / ref_speed:.3f}x)"
              + (f"; first divergence: {', '.join(diffs)}" if diffs else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
