#!/usr/bin/env python3
"""Validate fresh R2 route-screen artifacts with the checksum-pinned R1 gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
R2_RUNNER = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R2 = load(R2_RUNNER, "qwen36_mtp_route_8k_r2_runner_for_validator")
BASE = load(R2.R1_VALIDATOR, "qwen36_mtp_route_8k_r1_validator_for_r2")
BASE.CAMPAIGN_ID = R2.R2_CAMPAIGN_ID
BASE.load_runner = lambda: R2


def validate(root: Path, manifest_path: Path):
    R2.verify_references(R2.load_overlay())
    return BASE.validate(root, manifest_path)


def main() -> int:
    R2.verify_references(R2.load_overlay())
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
