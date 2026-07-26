#!/usr/bin/env python3
"""Fail-closed audit that a diagnostic ran the benchmark's workload.

Written after a rank-2 probe was accepted as a go/no-go and turned out to have
fed raw prompts through ``LLM.generate`` while the benchmark it was meant to
explain used chat completions with the model's chat template. Every prompt
differed by 40-41 tokens and every generated-token hash differed, so the
measured rate described a different workload.

The check that would have caught it in one second is the first one below. This
tool exists so that check is never skipped again, and it exits non-zero on any
mismatch rather than printing a warning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _sha(values: list[int]) -> str:
    return hashlib.sha256(",".join(str(v) for v in values).encode()).hexdigest()


def _rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("payload has no rows")
    return rows


def audit(benchmark: Path, probe: Path) -> list[str]:
    """Return every reason the probe does not match the benchmark workload."""
    bench = json.loads(benchmark.read_text())
    diag = json.loads(probe.read_text())
    brows, prows = _rows(bench), _rows(diag)
    failures: list[str] = []

    if len(brows) != len(prows):
        failures.append(f"prompt count {len(prows)} != benchmark {len(brows)}")
        return failures

    bp = [r.get("prompt_tokens") for r in brows]
    pp = [r.get("prompt_tokens") for r in prows]
    if bp != pp:
        deltas = [
            None if (a is None or b is None) else a - b for a, b in zip(bp, pp)
        ]
        failures.append(
            "prompt_tokens differ, so the request construction differs "
            f"(chat template?): benchmark={bp} probe={pp} delta={deltas}"
        )

    bc = [r.get("completion_tokens") for r in brows]
    pc = [r.get("completion_tokens") for r in prows]
    if bc != pc:
        failures.append(f"completion_tokens differ: benchmark={bc} probe={pc}")

    for index, (b, p) in enumerate(zip(brows, prows)):
        bt, pt = b.get("token_ids"), p.get("token_ids")
        if bt and pt and _sha(bt) != _sha(pt):
            failures.append(f"prompt {index}: generated-token hashes differ")

    for index, row in enumerate(prows):
        cached = row.get("cached_tokens")
        if cached not in (0, None):
            failures.append(f"prompt {index}: cached_tokens={cached}, not 0")

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", type=Path, required=True)
    ap.add_argument("--probe", type=Path, required=True)
    args = ap.parse_args()

    failures = audit(args.benchmark, args.probe)
    if failures:
        print("PROBE_IDENTITY=MISMATCH")
        for reason in failures:
            print(f"  - {reason}")
        print("\nThe probe did not run the benchmark workload. Any rate it")
        print("measured describes a different workload and cannot gate a")
        print("decision about the benchmark.")
        return 1
    print("PROBE_IDENTITY=MATCH")
    print("  prompt tokens, completion tokens, generated-token hashes, and")
    print("  cache-zero all agree with the benchmark run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
