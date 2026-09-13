#!/usr/bin/env python3
"""Read saved ladder evidence only; never discover or contact a device/server.

Exit 0 means the requested rows match the reference summary, NOT healthy teardown.
Exit 1 means incomplete/mismatched row evidence. Operational status is separate.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def audit(run, supervisor, reference, depths, repeats):
    inputs = {}

    def read(path):
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            inputs[str(path)] = None
            return ""
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return raw.decode()

    def summary(path):
        try:
            value = json.loads(read(path))
            return value if isinstance(value, dict) else {}
        except (ValueError, UnicodeError):
            return {}

    actual = summary(run / "depth-ladder.json")
    expected = summary(reference / "depth-ladder.json")
    errors = []
    rates = {}
    for depth in depths:
        rows, refs = actual.get(depth), expected.get(depth)
        if not isinstance(rows, list) or not isinstance(refs, list) or len(rows) != repeats or len(refs) != repeats:
            errors.append(f"{depth}: incomplete rows/reference")
            continue
        hashes = []
        for label, group in (("actual", rows), ("reference", refs)):
            for number, row in enumerate(group, 1):
                if not isinstance(row, dict):
                    errors.append(f"{depth}: malformed {label} row")
                    continue
                digest = row.get("output_token_ids_sha256")
                if row.get("row") != number or row.get("status") != "passed" or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    errors.append(f"{depth}: invalid {label} row {number}")
                hashes.append(digest)
        if any(h != hashes[0] for h in hashes[1:]):
            errors.append(f"{depth}: output hash mismatch")
        rates[depth] = [r.get("tok_s_99_intervals") for r in rows if isinstance(r, dict)]
        for number in range(1, repeats + 1):
            if read(run / f"exact-depth-{depth}-r{number}.rc").strip() != "0":
                errors.append(f"{depth}: missing/nonzero raw row exit {number}")
    rc = read(supervisor / "final.rc").strip()
    markers = [read(supervisor / name) for name in
               ["xpu-discovery.err"] + [f"xpu-stats-{i}.err" for i in range(4)]]
    cached = any("cached" in m.lower() or "bypassed" in m.lower() for m in markers)
    return {
        "schema": "flash-next.offline-ladder-audit.v1",
        "row_summary_comparison_passed": not errors,
        "row_errors": errors,
        "actual_decode_tok_s": rates,
        "supervisor_exit": rc or None,
        "cached_gpu_receipts_detected": cached,
        "teardown_status": "nonzero_exit" if rc and rc != "0" else "unverified",
        "device_health": "unverified",
        "scope": "Saved summaries and row exit files only; no raw token rehash, identity certification, or live health test.",
        "input_sha256": inputs,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "supervisor", "reference"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--depths", default="2k,8k,16k,32k")
    p.add_argument("--repeats", type=int, default=2)
    args = p.parse_args()
    if args.repeats < 1:
        p.error("repeats must be positive")
    result = audit(args.run, args.supervisor, args.reference, args.depths.split(","), args.repeats)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["row_summary_comparison_passed"] else 1)
