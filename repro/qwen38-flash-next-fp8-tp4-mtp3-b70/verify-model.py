#!/usr/bin/env python3
"""Verify the Flash-Next model against this repro's frozen model contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_ROOT / "model-contract.json"
VERIFIER_PATH = REPO_ROOT / "scripts/verify-qwen38-flash-next-fp8-tree.py"
CONTRACT_FORMAT = "qwen38-flash-next-fp8-model-contract-v1"


class ModelContractError(RuntimeError):
    """The repro contract and shared verifier disagree."""


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_verifier() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "qwen38_flash_next_model_verifier", VERIFIER_PATH
    )
    if specification is None or specification.loader is None:
        raise ModelContractError(f"cannot load model verifier: {VERIFIER_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        contract = json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
        )
        if contract.get("format") != CONTRACT_FORMAT:
            raise ModelContractError("unsupported model contract format")
        if contract.get("status") != "pre-publication":
            raise ModelContractError("model contract must remain pre-publication")
        verifier = load_verifier()
        if contract.get("contract") != asdict(verifier.PINNED):
            raise ModelContractError(
                "repro model contract differs from the shared frozen verifier"
            )
        return verifier.main(
            ["--model-root", str(args.model_root), "--receipt", str(args.receipt)]
        )
    except (OSError, ValueError, ModelContractError) as exc:
        print(f"verify-model: FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
