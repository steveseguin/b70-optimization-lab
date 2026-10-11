#!/usr/bin/env python3
"""Check literal shell SHA256 pins without running any experiment.

Default: report current-path drift and fail on every mismatch. Optional
--historical-manifest validates reviewed, byte-bound historical exceptions;
recovered and blocked history are reported separately from working live paths.
This is not a shell interpreter: variable-held hashes/paths, absolute paths,
and non-shell pins remain outside the scan. It does not certify full replay.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from historical_verifiers import scan_pins, validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--historical-manifest", type=Path)
    parser.add_argument("--json", action="store_true", help="print full findings as JSON")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        rows = scan_pins(root)
        review = (validate_manifest(root, args.historical_manifest, rows)
                  if args.historical_manifest else None)
    except (OSError, ValueError) as exc:
        print(f"pin audit failed: {exc}", file=sys.stderr)
        return 1
    counts = {kind: sum(row["status"] == kind for row in rows)
              for kind in ("match", "drift", "absent")}
    if args.json:
        print(json.dumps({"scope": "git-tracked literal shell file pins",
                          "counts": counts, "historical_review": review,
                          "pins": rows}, indent=2))
    else:
        print(f"checked {len(rows)} literal file pins: {counts['match']} match, "
              f"{counts['drift']} drifted, {counts['absent']} target absent")
        if review:
            print(f"historical review: {review['recoverable']} recoverable, "
                  f"{review['blocked']} explicitly blocked; "
                  f"{review['maintained_replays']} maintained verifier identities match")
            print("Original historical paths still drift; recovery does not qualify a GPU replay.")
        if not args.quiet:
            seen = set()
            for row in rows:
                key = (row["status"], row["target"], row["expected_sha256"])
                if row["status"] == "match" or key in seen:
                    continue
                seen.add(key)
                print(f"  {row['status'].upper():6s} {row['target']}")
                print(f"         expected {row['expected_sha256']}; pinned by {row['holder']}")
            print("Scope excludes variable-held/absolute/non-shell pins and runtime dependencies.")
    return 0 if review is not None else int(bool(counts["drift"] or counts["absent"]))


if __name__ == "__main__":
    raise SystemExit(main())
