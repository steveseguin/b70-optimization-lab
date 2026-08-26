#!/usr/bin/env python3
"""Read-only validator for the current-image AutoRound E5M2-KV closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1-result.json"
ERROR = "NotImplementedError: FlashAttention does not support fp8_e5m2 kv-cache on this device."


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "unsupported", "compact result is not unsupported")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["state"] == "unsupported" and terminal["runner_return_code"] == 42, "terminal classification changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "protected authority widened")
    need(not terminal["automatic_descendant_expansion"], "automatic descendants were enabled")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm receipt changed")
    need(arm["state"] == "unsupported" and arm["reason"] == "explicit-e5m2-kv-dtype-rejection", "arm classification changed")
    need(arm["runner_return_code"] == 42 and arm["exact_canary_128_return_code"] == 125 and arm["quality_return_code"] == 125, "phase return codes changed")
    need(not arm["startup_identity_passed"] and not arm["descendant_execution_authorized"] and not arm["descendant_expansion_authorized"], "unsupported authority widened")
    need(arm["cleanup_passed"], "cleanup did not pass")

    server_log = root / "server.log"
    need(digest(server_log) == result["failure"]["server_log_sha256"], "server log changed")
    need(ERROR in server_log.read_text(encoding="utf-8", errors="replace"), "exact E5M2 rejection disappeared")
    need(not (root / "exact-depth").exists() and not (root / "quality.json").exists(), "canary or quality unexpectedly exists")

    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in verification["files"]), "model read paths weakened")

    scope = result["scope"]
    need(scope["unsupported_cells"] == 7 and scope["selectors"] == {"tp": 1, "mtp": 0, "graph_mode": "off", "kv": "fp8_e5m2", "active_context_tokens": [0, 2048, 4096, 8192, 16384, 24576, 32768]}, "unsupported scope widened")
    need(not scope["graph_tp_mtp_or_other_runtime_transfer"] and scope["older_e9d_unsupported_closure_retained"], "runtime scope changed")
    authority = result["authority"]
    need(authority["measured_cells"] == 0 and authority["estimated_cells"] == 0 and authority["unsupported_cells"] == 7, "authority changed")
    need(not authority["headline_or_protected_replacement"], "protected replacement was authorized")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "classification": "unsupported", "cells_closed": 7, "canary": "not-run", "quality": "not-run"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
