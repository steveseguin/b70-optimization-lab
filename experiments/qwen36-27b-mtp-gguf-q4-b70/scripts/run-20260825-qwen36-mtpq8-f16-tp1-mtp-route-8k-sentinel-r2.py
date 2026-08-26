#!/usr/bin/env python3
"""R2 retry of the 8K MTP route screen; only ldd indentation handling changes."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2-prereg.json"
R1_MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1-prereg.json"
R1_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"
R1_VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"
R1_TERMINAL = Path("/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1/terminal-receipt.json")
R2_CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r2"
R2_ROOT = "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r2"
R2_RUNNER_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"
R2_VALIDATOR_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_overlay(value: dict[str, Any]) -> None:
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp-route-8k-sentinel-r2-retry-overlay.v1"
        and value.get("campaign_id") == R2_CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sole_execution_delta", {}).get(
            "model_runtime_dso_environment_arms_workload_gate_or_authority_delta"
        ) is False
        and value.get("r2_lifecycle", {}).get("output_root") == R2_ROOT
        and value.get("r2_lifecycle", {}).get("exact_ack") == f"RUN {R2_CAMPAIGN_ID}"
        and value.get("frozen_interpretation", {}).get("r1_route_authority") == []
        and value.get("frozen_interpretation", {}).get("site_or_family_edit_authorized") is False
    ):
        raise RuntimeError("R2 overlay invariant failed")


def load_overlay() -> dict[str, Any]:
    value = json.loads(OVERLAY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("R2 overlay must be an object")
    validate_overlay(value)
    return value


def verify_references(overlay: dict[str, Any]) -> None:
    base = overlay["base_packet"]
    failure = overlay["r1_failure"]
    for path, expected, label in (
        (R1_MANIFEST, base["manifest_sha256"], "R1 manifest"),
        (R1_RUNNER, base["runner_sha256"], "R1 runner"),
        (R1_VALIDATOR, base["validator_sha256"], "R1 validator"),
        (R1_TERMINAL, failure["terminal_receipt_sha256"], "R1 terminal"),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"{label} changed: {path}")
    terminal = json.loads(R1_TERMINAL.read_text(encoding="utf-8"))
    if not (
        terminal.get("campaign_id") == "qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1"
        and terminal.get("status") == failure["required_status"]
        and terminal.get("error") == failure["required_error"]
        and terminal.get("authority", {}).get("curve_expansion_routes") == []
    ):
        raise RuntimeError("R1 failure receipt invariant failed")


def merge_manifest(overlay: dict[str, Any]) -> dict[str, Any]:
    r1_overlay = copy.deepcopy(json.loads(R1_MANIFEST.read_text(encoding="utf-8")))
    value = BASE.merged_manifest(r1_overlay)
    value["campaign_id"] = R2_CAMPAIGN_ID
    value["purpose"] += " R2 is a fresh retry whose sole execution delta accepts leading whitespace in ldd rows."
    value["lifecycle"]["runner"] = R2_RUNNER_REL
    value["lifecycle"]["validator"] = R2_VALIDATOR_REL
    value["lifecycle"]["output_root"] = R2_ROOT
    value["lifecycle"]["exact_ack"] = f"RUN {R2_CAMPAIGN_ID}"
    value["retry_overlay"] = {
        "schema": overlay["schema"],
        "r1_terminal_receipt_sha256": overlay["r1_failure"]["terminal_receipt_sha256"],
        "sole_execution_delta": overlay["sole_execution_delta"],
        "r1_rows_reused": False,
    }
    return value


def transformed_source() -> str:
    source = R1_RUNNER.read_text(encoding="utf-8")
    replacements = (
        ("qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1", R2_CAMPAIGN_ID, 2),
        ("2026-08-25-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1-prereg.json", OVERLAY.name, 1),
        ("validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py", Path(R2_VALIDATOR_REL).name, 1),
        ('rf"^{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"',
         'rf"^\\s*{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"', 1),
    )
    for old, new, expected_count in replacements:
        count = source.count(old)
        if count != expected_count:
            raise RuntimeError(f"R1 transform count drift for {old!r}: {count}")
        source = source.replace(old, new)
    return source


def load_transformed_base() -> tuple[ModuleType, str]:
    source = transformed_source()
    module = ModuleType("qwen36_mtp_route_8k_r2_transformed")
    module.__file__ = str(R1_RUNNER)
    module.__package__ = None
    sys.modules[module.__name__] = module
    exec(compile(source, str(R1_RUNNER), "exec"), module.__dict__)
    def transformed_load_overlay() -> dict[str, Any]:
        return merge_manifest(load_overlay())

    module.load_overlay = transformed_load_overlay
    return module, source


OVERLAY_VALUE = load_overlay()
verify_references(OVERLAY_VALUE)
BASE, TRANSFORMED_SOURCE = load_transformed_base()
TRANSFORMED_SOURCE_SHA256 = hashlib.sha256(TRANSFORMED_SOURCE.encode("utf-8")).hexdigest()
merged_manifest = merge_manifest


def main() -> int:
    overlay = load_overlay()
    verify_references(overlay)
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
