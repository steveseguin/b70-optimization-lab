#!/usr/bin/env python3
"""Validate the fresh R2 MTP1 parent sentinel without reusing R1 rows."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"
BASE_VALIDATOR = LANE / "scripts/validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py"
R1_FAILURE = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.json"
R1_TERMINAL = Path(
    "/mnt/fast-ai/bench-results/qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1/terminal-receipt.json"
)
CAMPAIGN_ID = "qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_module():
    spec = importlib.util.spec_from_file_location("qwen36_mtp1_parent_r1_validator", BASE_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module()
ORIGINAL_LOAD_JSON = BASE.load_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return ORIGINAL_LOAD_JSON(path)


def verify_reference(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise BASE.GateError(f"referenced {label} changed: {path}")


def load_overlay(path: Path) -> dict[str, Any]:
    if path.resolve() != OVERLAY.resolve():
        raise BASE.GateError("R2 requires the frozen overlay manifest")
    overlay = load_json(path)
    if not (
        overlay.get("schema")
        == "neural.download.qwen36-llama-mtp1-parent-sentinel-r2-overlay.v1"
        and overlay.get("campaign_id") == CAMPAIGN_ID
        and overlay.get("state") == "preregistered-not-launched"
        and overlay.get("r1_failure", {}).get("rows_reused") is False
        and overlay.get("r2_lifecycle", {}).get("fresh_both_arms") is True
        and overlay.get("r2_lifecycle", {}).get("r1_root_is_read_only") is True
        and overlay.get("frozen_interpretation", {}).get("speed_floor") is None
        and overlay.get("frozen_interpretation", {}).get("cell_gain_on_sentinel_pass") == 0
        and overlay.get("frozen_interpretation", {}).get("r1_measurement_transfer_allowed")
        is False
        and overlay.get("frozen_interpretation", {}).get("site_or_family_edit_authorized")
        is False
    ):
        raise BASE.GateError("R2 overlay invariant failed")

    base = overlay["base_packet"]
    failure = overlay["r1_failure"]
    references = (
        (REPO / base["manifest"], base["manifest_sha256"], "R1 manifest"),
        (REPO / base["runner"], base["runner_sha256"], "R1 runner"),
        (REPO / base["validator"], base["validator_sha256"], "R1 validator"),
        (
            REPO / base["preregistration_note"],
            base["preregistration_note_sha256"],
            "R1 preregistration note",
        ),
        (REPO / failure["failure_record"], failure["failure_record_sha256"], "R1 failure record"),
        (REPO / failure["failure_note"], failure["failure_note_sha256"], "R1 failure note"),
        (R1_TERMINAL, failure["terminal_receipt_sha256"], "R1 terminal receipt"),
    )
    for reference, expected, label in references:
        verify_reference(reference, expected, label)
    return overlay


def expanded_manifest(overlay: dict[str, Any]) -> dict[str, Any]:
    expanded = copy.deepcopy(load_json(BASE_MANIFEST))
    lifecycle = overlay["r2_lifecycle"]
    quality = overlay["quality_environment"]
    expanded["campaign_id"] = CAMPAIGN_ID
    expanded["purpose"] = overlay["purpose"]
    expanded["clients"]["quality"]["interpreter"] = quality["interpreter"]
    expanded["clients"]["quality"]["interpreter_realpath"] = quality[
        "interpreter_realpath"
    ]
    expanded["clients"]["quality"]["python_version"] = quality["python_version"]
    expanded["lifecycle"]["runner"] = lifecycle["runner"]
    expanded["lifecycle"]["validator"] = lifecycle["validator"]
    expanded["lifecycle"]["output_root"] = lifecycle["output_root"]
    expanded["lifecycle"]["exact_ack"] = lifecycle["exact_ack"]
    return expanded


def expected_quality_capability(overlay: dict[str, Any]) -> dict[str, Any]:
    quality = overlay["quality_environment"]
    return {
        "interpreter": quality["interpreter"],
        "interpreter_realpath": quality["interpreter_realpath"],
        "interpreter_sha256": quality["interpreter_sha256"],
        "sys_prefix": quality["sys_prefix"],
        "python_version": quality["python_version"],
        "pyvenv_cfg": {
            "path": quality["pyvenv_cfg"],
            "sha256": quality["pyvenv_cfg_sha256"],
        },
        "transformers": quality["transformers"],
        "tokenizers": quality["tokenizers"],
        "numpy": quality["numpy"],
        "offline_tokenizer_probe": quality["offline_tokenizer_probe"],
    }


def validate(
    root: Path, manifest_path: Path, *, enforce_output_root: bool = True
) -> dict[str, Any]:
    overlay = load_overlay(manifest_path)
    expanded = expanded_manifest(overlay)

    def intercepted_load_json(path: Path) -> dict[str, Any]:
        if path.resolve() == OVERLAY.resolve():
            return copy.deepcopy(expanded)
        return ORIGINAL_LOAD_JSON(path)

    prior_campaign = BASE.CAMPAIGN_ID
    prior_loader = BASE.load_json
    BASE.CAMPAIGN_ID = CAMPAIGN_ID
    BASE.load_json = intercepted_load_json
    try:
        result = BASE.validate(root, manifest_path)
    finally:
        BASE.CAMPAIGN_ID = prior_campaign
        BASE.load_json = prior_loader

    checks = result["gate"]["checks"]
    expected_root = Path(overlay["r2_lifecycle"]["output_root"])
    checks["r2_output_root_exact"] = (
        not enforce_output_root or root.resolve() == expected_root.resolve()
    )
    identity_path = root / "identity.txt"
    identity_lines = set(identity_path.read_text(encoding="utf-8", errors="replace").splitlines())
    capability = expected_quality_capability(overlay)
    capability_line = "quality_environment=" + json.dumps(
        capability, separators=(",", ":"), sort_keys=True
    )
    checks["pinned_quality_environment_captured"] = capability_line in identity_lines
    checks["r2_campaign_identity_captured"] = f"campaign_id={CAMPAIGN_ID}" in identity_lines
    checks["r2_run_root_identity_captured"] = (
        f"r2_run_root={expected_root}" in identity_lines
    )
    transformed_rows = [
        line.removeprefix("transformed_runner_sha256=")
        for line in identity_lines
        if line.startswith("transformed_runner_sha256=")
    ]
    checks["transformed_runner_identity_captured"] = (
        len(transformed_rows) == 1
        and SHA256_RE.fullmatch(transformed_rows[0]) is not None
        and transformed_rows[0]
        == overlay["r2_lifecycle"]["transformed_runner_sha256"]
    )

    quality_stderr = root / overlay["r2_lifecycle"]["quality_stderr_artifact"]
    checks["quality_stderr_artifact_captured"] = quality_stderr.is_file()
    r1 = load_json(R1_FAILURE)["completed_exact_depth_arms"]
    control_sha = sha256_file(root / "control-mtp0/exact-depth.json")
    candidate_sha = sha256_file(root / "candidate-mtp1/exact-depth.json")
    checks["r1_exact_depth_rows_not_reused"] = (
        control_sha != r1["control_mtp0"]["receipt_sha256"]
        and candidate_sha != r1["candidate_mtp1"]["receipt_sha256"]
    )
    r1_terminal_created = dt.datetime.fromisoformat(load_json(R1_TERMINAL)["created_at_utc"])
    fresh_receipts = (
        load_json(root / "control-mtp0/exact-depth.json"),
        load_json(root / "candidate-mtp1/exact-depth.json"),
    )
    try:
        fresh_created = [
            dt.datetime.fromisoformat(receipt["created_at_utc"])
            for receipt in fresh_receipts
        ]
    except (KeyError, TypeError, ValueError):
        fresh_created = []
    checks["fresh_receipts_postdate_r1_terminal"] = (
        len(fresh_created) == 2
        and all(value.tzinfo is not None for value in fresh_created)
        and all(value > r1_terminal_created for value in fresh_created)
    )

    passed = all(checks.values())
    result["gate"]["passed"] = passed
    result["status"] = (
        "passed-expand-mtp1-depth-curve" if passed else "failed-do-not-expand"
    )
    result["quality_environment"] = {
        "capability": capability,
        "stderr_path": str(quality_stderr),
        "stderr_sha256": sha256_file(quality_stderr) if quality_stderr.is_file() else None,
    }
    result["r1_preservation"] = {
        "run_root": overlay["r1_failure"]["run_root"],
        "terminal_receipt_sha256": sha256_file(R1_TERMINAL),
        "rows_reused": False,
        "r1_target_output_parity_passed": False,
    }
    result["transformed_runner_sha256"] = (
        transformed_rows[0] if len(transformed_rows) == 1 else None
    )
    result["interpretation"] = (
        "Prepare a separate preregistered seven-depth MTP1 HTTP-serving curve. "
        "R1 remains failed and contributed no row."
        if passed
        else "Do not expand MTP1; preserve R1 and R2 as separate failed evidence."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["gate"]["passed"] else 2
    except (BASE.GateError, KeyError, OSError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
