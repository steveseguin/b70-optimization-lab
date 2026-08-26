#!/usr/bin/env python3
"""R2 overlay for the R1 MTP3 curve; only ldd indentation handling changes."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2-prereg.json"
R1_MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1-prereg.json"
R1_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py"
R1_VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py"
R1_FAILURE = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1-pre-gpu-failure.json"
R1_TERMINAL = Path("/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r1/terminal-receipt.json")
R2_CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r2"
R2_ROOT = "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r2"
R2_RUNNER_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R2_VALIDATOR_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_overlay() -> dict[str, Any]:
    value = json.loads(OVERLAY.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not (
        value.get("schema") == "neural.download.qwen36-llama-mtp3-exact-depth-r2-retry-overlay.v1"
        and value.get("campaign_id") == R2_CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sole_execution_delta", {}).get("model_runtime_dso_or_workload_delta") is False
        and value.get("r2_lifecycle", {}).get("output_root") == R2_ROOT
        and value.get("r2_lifecycle", {}).get("exact_ack") == f"RUN {R2_CAMPAIGN_ID}"
    ):
        raise RuntimeError("R2 overlay invariant failed")
    return value


def verify_references(overlay: dict[str, Any]) -> None:
    base = overlay["base_packet"]
    failure = overlay["r1_failure"]
    references = (
        (R1_MANIFEST, base["manifest_sha256"], "R1 manifest"),
        (R1_RUNNER, base["runner_sha256"], "R1 runner"),
        (R1_VALIDATOR, base["validator_sha256"], "R1 validator"),
        (R1_FAILURE, failure["failure_record_sha256"], "R1 failure record"),
        (R1_TERMINAL, failure["terminal_receipt_sha256"], "R1 terminal"),
    )
    for path, expected, label in references:
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"{label} changed: {path}")


def merge_manifest(overlay: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(json.loads(R1_MANIFEST.read_text(encoding="utf-8")))
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
        ("qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r1", R2_CAMPAIGN_ID),
        ("2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1-prereg.json", OVERLAY.name),
        ("validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py", Path(R2_VALIDATOR_REL).name),
        ('rf"^{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"', 'rf"^\\s*{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"'),
    )
    for old, new in replacements:
        count = source.count(old)
        if count != 1:
            raise RuntimeError(f"R1 transform count drift for {old!r}: {count}")
        source = source.replace(old, new)
    return source


def load_transformed_base() -> tuple[ModuleType, str]:
    source = transformed_source()
    module = ModuleType("qwen36_mtp3_exact_depth_r2_transformed")
    module.__file__ = str(R1_RUNNER)
    module.__package__ = None
    sys.modules[module.__name__] = module
    exec(compile(source, str(R1_RUNNER), "exec"), module.__dict__)
    original_load_json = module.load_json

    def load_json(path: Path) -> dict[str, Any]:
        if Path(path).resolve() == OVERLAY.resolve():
            return merge_manifest(load_overlay())
        return original_load_json(path)

    module.load_json = load_json
    return module, source


OVERLAY_VALUE = load_overlay()
verify_references(OVERLAY_VALUE)
BASE, TRANSFORMED_SOURCE = load_transformed_base()
TRANSFORMED_SOURCE_SHA256 = hashlib.sha256(TRANSFORMED_SOURCE.encode("utf-8")).hexdigest()


def main() -> int:
    overlay = load_overlay()
    verify_references(overlay)
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
