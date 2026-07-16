#!/usr/bin/env python3
"""Freeze a DeepSeek speculative candidate before held-out pack generation.

The output is created exclusively and made read-only.  A held-out evaluator
must reject any candidate whose current identities or artifacts no longer hash
to this manifest.  The held-out seed is intentionally absent: it is selected
only after this file exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--candidate-identity", type=Path, required=True)
    parser.add_argument("--target-control-identity", type=Path, required=True)
    parser.add_argument("--mtp1-control-identity", type=Path, required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        action="append",
        default=[],
        help="Candidate patch, policy, draft, router, or other frozen artifact",
    )
    parser.add_argument(
        "--allowed-policy-input",
        action="append",
        default=[],
        help="Information the online policy may inspect before target verification",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    required = [
        args.contract,
        args.candidate_identity,
        args.target_control_identity,
        args.mtp1_control_identity,
        *args.artifact,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite frozen manifest: {args.out}")

    def record(path: Path) -> dict[str, str | int]:
        resolved = path.resolve()
        return {
            "path": str(resolved),
            "sha256": sha256(resolved),
            "bytes": resolved.stat().st_size,
        }

    payload = {
        "schema_version": 1,
        "classification": "deepseek_spec_candidate_frozen_before_holdout",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "holdout_seed_materialized": False,
        "contract": record(args.contract),
        "candidate_identity": record(args.candidate_identity),
        "controls": {
            "target_only": record(args.target_control_identity),
            "current_mtp1": record(args.mtp1_control_identity),
        },
        "candidate_artifacts": [record(path) for path in args.artifact],
        "allowed_policy_inputs": sorted(set(args.allowed_policy_input)),
        "rules": {
            "overwrite_forbidden": True,
            "candidate_change_spends_materialized_pack": True,
            "suite_labels_prompt_hashes_saved_outputs_future_target_data_forbidden": True,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(args.out, flags, 0o444)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
