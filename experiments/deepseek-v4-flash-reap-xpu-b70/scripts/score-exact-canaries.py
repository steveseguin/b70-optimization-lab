#!/usr/bin/env python3
"""Score the ordered exact-output DeepSeek promotion canaries.

The default mode preserves the historical scorer's permissive behavior. New
evidence should use ``--strict`` or ``--strict-contract`` so row identity and
order cannot be changed without failing the score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


STRICT_CONTRACT_SCHEMA = "deepseek-v4-exact-canary-score-contract-v1"
DECODING_FIELDS = ("seed", "max_tokens", "top_logprobs")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(encoded)


def duplicate_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        prompt_id = row.get("id")
        if isinstance(prompt_id, str) and prompt_id in seen:
            duplicates.add(prompt_id)
        elif isinstance(prompt_id, str):
            seen.add(prompt_id)
    return sorted(duplicates)


def capture_decoding(capture: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return one decoding identity and flag conflicting duplicate fields."""

    nested = capture.get("decoding")
    nested = nested if isinstance(nested, dict) else {}
    identity: dict[str, Any] = {}
    errors: list[str] = []
    for field in DECODING_FIELDS:
        top_level = capture.get(field)
        nested_value = nested.get(field)
        if field in capture and field in nested and top_level != nested_value:
            errors.append(f"capture decoding {field} conflicts with top-level field")
        if field in nested:
            identity[field] = nested_value
        elif field in capture:
            identity[field] = top_level
    return identity, errors


def load_strict_contract(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("strict contract must be a JSON object")
    if value.get("schema") != STRICT_CONTRACT_SCHEMA:
        raise ValueError(f"strict contract schema must be {STRICT_CONTRACT_SCHEMA!r}")
    allowed = {
        "schema",
        "suite_sha256",
        "suite_id",
        "model",
        "model_revision",
        "decoding",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"unknown strict contract fields: {unknown}")
    suite_sha = value.get("suite_sha256")
    if not isinstance(suite_sha, str) or len(suite_sha) != 64:
        raise ValueError("strict contract suite_sha256 must be 64 hex characters")
    try:
        int(suite_sha, 16)
    except ValueError as exc:
        raise ValueError(
            "strict contract suite_sha256 must be 64 hex characters"
        ) from exc
    decoding = value.get("decoding")
    for field in ("suite_id", "model", "model_revision"):
        if field in value and (not isinstance(value[field], str) or not value[field]):
            raise ValueError(f"strict contract {field} must be a non-empty string")
    if decoding is not None:
        if not isinstance(decoding, dict):
            raise ValueError("strict contract decoding must be an object")
        unknown_decoding = sorted(set(decoding) - set(DECODING_FIELDS))
        if unknown_decoding:
            raise ValueError(
                f"unknown strict contract decoding fields: {unknown_decoding}"
            )
        for field, item in decoding.items():
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                raise ValueError(
                    f"strict contract decoding {field} must be a non-negative integer"
                )
        if "max_tokens" in decoding and decoding["max_tokens"] == 0:
            raise ValueError("strict contract decoding max_tokens must be positive")
    return value


def strict_errors(
    capture: dict[str, Any],
    suite: dict[str, Any],
    suite_sha256: str,
    contract: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    rows = capture.get("rows")
    prompts = suite.get("prompts")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return ["capture rows must be a list of objects"]
    if not isinstance(prompts, list) or not all(
        isinstance(prompt, dict) for prompt in prompts
    ):
        return ["suite prompts must be a list of objects"]

    capture_duplicates = duplicate_ids(rows)
    suite_duplicates = duplicate_ids(prompts)
    if capture_duplicates:
        errors.append(f"duplicate capture IDs: {capture_duplicates}")
    if suite_duplicates:
        errors.append(f"duplicate suite IDs: {suite_duplicates}")

    expected_ids = [prompt.get("id") for prompt in prompts]
    observed_ids = [row.get("id") for row in rows]
    expected_ids_valid = all(isinstance(value, str) and value for value in expected_ids)
    observed_ids_valid = all(isinstance(value, str) and value for value in observed_ids)
    if not prompts:
        errors.append("suite prompts must not be empty")
    if not rows:
        errors.append("capture rows must not be empty")
    if not expected_ids_valid:
        errors.append("suite prompt IDs must be non-empty strings")
    if not observed_ids_valid:
        errors.append("capture row IDs must be non-empty strings")
    if (
        expected_ids_valid
        and observed_ids_valid
        and not capture_duplicates
        and not suite_duplicates
    ):
        missing = sorted(set(expected_ids) - set(observed_ids))
        extra = sorted(set(observed_ids) - set(expected_ids))
        if missing:
            errors.append(f"missing capture IDs: {missing}")
        if extra:
            errors.append(f"extra capture IDs: {extra}")
        if not missing and not extra and observed_ids != expected_ids:
            errors.append("capture IDs are out of suite order")

    for prompt, row in zip(prompts, rows):
        prompt_text = prompt.get("prompt")
        if not isinstance(prompt_text, str):
            errors.append(f"suite prompt {prompt.get('id')!r} has no string prompt")
            continue
        expected_prompt_sha = sha256_bytes(prompt_text.encode("utf-8"))
        if row.get("prompt_sha256") != expected_prompt_sha:
            errors.append(f"prompt SHA-256 mismatch for {prompt.get('id')!r}")
        if row.get("cached_tokens") != 0:
            errors.append(f"cached_tokens is not zero for {row.get('id')!r}")

    suite_meta = {key: value for key, value in suite.items() if key != "prompts"}
    if capture.get("suite") != suite_meta:
        errors.append("embedded capture suite metadata does not match suite")
    if capture.get("suite_sha256") != suite_sha256:
        errors.append("capture suite_sha256 does not match suite bytes")

    decoding, decoding_errors = capture_decoding(capture)
    errors.extend(decoding_errors)
    if contract is not None:
        if contract["suite_sha256"] != suite_sha256:
            errors.append("strict contract suite_sha256 does not match suite bytes")
        for field in ("suite_id", "model", "model_revision"):
            if field in contract:
                observed = (
                    suite.get("suite_id") if field == "suite_id" else capture.get(field)
                )
                if observed != contract[field]:
                    errors.append(f"capture {field} does not match strict contract")
        for field, expected in (contract.get("decoding") or {}).items():
            if decoding.get(field) != expected:
                errors.append(
                    f"capture decoding {field} does not match strict contract"
                )
    return errors


def score(
    capture: dict[str, Any],
    suite: dict[str, Any],
    *,
    capture_path: str,
    suite_path: str,
    suite_sha256: str,
    strict: bool,
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    rows = capture.get("rows")
    prompts = suite.get("prompts")
    if not isinstance(rows, list) or not isinstance(prompts, list):
        integrity_errors = ["capture rows and suite prompts must be lists"]
        observed: dict[str, str] = {}
        expected: dict[str, str] = {}
    else:
        integrity_errors = (
            strict_errors(capture, suite, suite_sha256, contract) if strict else []
        )
        observed = {
            row["id"]: str(row.get("content") or "").strip()
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        expected = {
            row["id"]: row["expected"]
            for row in prompts
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and isinstance(row.get("expected"), str)
        }
    exact_by_id = {
        prompt_id: observed.get(prompt_id) == value
        for prompt_id, value in expected.items()
    }
    cache_zero = capture.get("cached_tokens_all_zero") is True
    passed = cache_zero and all(exact_by_id.values()) and not integrity_errors
    return {
        "capture": capture_path,
        "suite": suite_path,
        "suite_sha256": suite_sha256,
        "strict": strict,
        "strict_contract_schema": contract.get("schema") if contract else None,
        "strict_contract_canonical_sha256": (
            canonical_sha256(contract) if contract else None
        ),
        "capture_integrity_errors": integrity_errors,
        "capture_integrity_passed": not integrity_errors,
        "cached_tokens_all_zero": cache_zero,
        "exact_by_id": exact_by_id,
        "observed": observed,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="require exact row set/order, prompt hashes, suite hash, and cache-zero rows",
    )
    parser.add_argument(
        "--strict-contract",
        type=Path,
        help=(
            "JSON contract binding suite hash and optional model, revision, and "
            "decoding identity; implies --strict"
        ),
    )
    args = parser.parse_args(argv)

    capture_raw = args.capture.read_bytes()
    suite_raw = args.suite.read_bytes()
    capture = json.loads(capture_raw)
    suite = json.loads(suite_raw)
    contract = (
        load_strict_contract(args.strict_contract) if args.strict_contract else None
    )
    result = score(
        capture,
        suite,
        capture_path=str(args.capture),
        suite_path=str(args.suite),
        suite_sha256=sha256_bytes(suite_raw),
        strict=args.strict or contract is not None,
        contract=contract,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
