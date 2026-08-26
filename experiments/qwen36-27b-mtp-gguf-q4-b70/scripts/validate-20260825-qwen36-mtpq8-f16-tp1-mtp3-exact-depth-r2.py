#!/usr/bin/env python3
"""Validate fresh R2 artifacts while reusing the checksum-pinned R1 gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
R2_RUNNER = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"


spec = importlib.util.spec_from_file_location("qwen36_mtp3_r2_runner_for_validator", R2_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import R2 runner")
R2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R2
spec.loader.exec_module(R2)

base_spec = importlib.util.spec_from_file_location("qwen36_mtp3_r1_validator_for_r2", R2.R1_VALIDATOR)
if base_spec is None or base_spec.loader is None:
    raise RuntimeError("cannot import R1 validator")
BASE = importlib.util.module_from_spec(base_spec)
sys.modules[base_spec.name] = BASE
base_spec.loader.exec_module(BASE)
ORIGINAL_LOAD_JSON = BASE.load_json
BASE.CAMPAIGN_ID = R2.R2_CAMPAIGN_ID


def load_json(path: Path):
    if Path(path).resolve() == R2.OVERLAY.resolve():
        overlay = R2.load_overlay()
        R2.verify_references(overlay)
        return R2.merge_manifest(overlay)
    return ORIGINAL_LOAD_JSON(path)


BASE.load_json = load_json


def validate(root: Path, manifest_path: Path):
    return BASE.validate(root, manifest_path)


def main() -> int:
    R2.verify_references(R2.load_overlay())
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
