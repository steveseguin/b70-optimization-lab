#!/usr/bin/env python3
"""Validate the Qwen estimate retirement and exact-8K graph closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
FAMILY_PATH = ROOT / "families/qwen-27b.json"
ADJUDICATION_PATH = ROOT / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-retired-estimates-q8kv-graph-8k-closure-adjudication.json"
)
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(rule: dict[str, Any], selectors: dict[str, Any]) -> bool:
    return all(value == "*" or selectors.get(key) == value for key, value in rule["match"].items())


def resolve(rules: list[dict[str, Any]], selectors: dict[str, Any]) -> dict[str, Any]:
    selected = [rule for rule in rules if matches(rule, selectors)]
    selected.sort(key=lambda rule: sum(value != "*" for value in rule["match"].values()))
    result: dict[str, Any] = {"selectors": selectors}
    for rule in selected:
        result.update({key: value for key, value in rule.items() if key not in {"id", "match"}})
    result["rule_ids"] = [rule["id"] for rule in selected]
    return result


def validate(
    family: dict[str, Any], adjudication: dict[str, Any], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    cleanup = adjudication.get("estimate_registry_cleanup", {})
    if cleanup.get("removed_entry_count") != 14:
        errors.append("adjudication must retire exactly 14 estimate entries")
    if cleanup.get("depths") != DEPTHS:
        errors.append("estimate retirement depths changed")
    if family.get("estimates") != []:
        errors.append("the live family estimate registry must be empty")

    contract = next(
        (item for item in family.get("coverage_contracts", [])
         if item.get("id") == "qwen38-tp1-llamacpp-sycl-target-matrix"),
        None,
    )
    if contract is None:
        return errors + ["target coverage contract is missing"]
    rules = contract.get("rules", [])

    for group in cleanup.get("groups", []):
        snapshot = group.get("historical_snapshot", {})
        snapshot_path = root / snapshot.get("path", "")
        if not snapshot_path.is_file() or sha256(snapshot_path) != snapshot.get("sha256"):
            errors.append(f"historical snapshot hash mismatch: {snapshot.get('path')}")
        for depth in DEPTHS:
            selectors = {
                "revision": "qwen3.8-27b",
                "artifact_id": group.get("artifact_id"),
                "tp": 1,
                "mtp": 0,
                "active_context_tokens": depth,
                "graph_mode": "off",
                "kv": "q8_0",
            }
            cell = resolve(rules, selectors)
            if cell.get("state") != "lab-measured":
                errors.append(f"retired selector is not measured: {selectors}")
            if cell.get("evidence_id") != group.get("replacement_evidence_id"):
                errors.append(f"retired selector has wrong measurement: {selectors}")
            expected_rule = f"{group.get('replacement_rule_id_prefix')}{depth}"
            if expected_rule not in cell.get("rule_ids", []):
                errors.append(f"retired selector lacks exact rule {expected_rule}")

        calibration = group.get("historical_calibration")
        if calibration:
            calibration_path = root / calibration.get("path", "")
            if not calibration_path.is_file() or sha256(calibration_path) != calibration.get("sha256"):
                errors.append("historical calibration hash mismatch")
            else:
                actual = load_json(calibration_path).get("summary", {})
                if actual.get("band_hits") != 0 or actual.get("band_misses") != 7:
                    errors.append("historical negative calibration changed")

    closure = adjudication.get("q8weights_q8kv_graph_cache64_8k_closure", {})
    source = closure.get("source_result", {})
    source_path = root / source.get("path", "")
    if not source_path.is_file() or sha256(source_path) != source.get("sha256"):
        errors.append("graph sentinel source hash mismatch")
    else:
        result = load_json(source_path)
        candidate = result.get("matched_8k", {}).get("candidate_graph_on_cache64", {})
        parity = result.get("matched_8k", {}).get("parity", {})
        quality = result.get("quality", {}).get("candidate_graph_on_cache64", {})
        authority = result.get("frozen_authority", {})
        if not candidate.get("gate_passed") or candidate.get("cached_tokens") != 0:
            errors.append("exact 8K graph candidate gate did not pass")
        if not all(parity.get(key) for key in ("output_token_ids", "text", "usage")):
            errors.append("exact 8K graph parity is incomplete")
        if quality.get("pass_all") is not False or "qptr->wait" not in quality.get("source_failure", ""):
            errors.append("expected long-quality qptr->wait failure is absent")
        if authority.get("site_cells") != 0 or authority.get("performance_cells") != 0:
            errors.append("source result unexpectedly authorizes performance")
        if authority.get("full_q8kv_graph_curve_design_closed") is not True:
            errors.append("source result does not close the graph design")

    base_selectors = {
        "revision": "qwen3.8-27b",
        "artifact_id": "qwen38-27b-ggmlorg-q8-0-0669b98",
        "tp": 1,
        "mtp": 0,
        "graph_mode": "SYCL",
        "kv": "q8_0",
    }
    for depth in DEPTHS:
        cell = resolve(rules, {**base_selectors, "active_context_tokens": depth})
        expected = "closed" if depth == 8192 else "missing"
        if cell.get("state") != expected:
            errors.append(f"graph/Q8-KV depth {depth} must remain {expected}")
        if depth == 8192:
            if cell.get("packet_id") != closure.get("packet_id"):
                errors.append("closed 8K cell is not bound to the closed packet")
            if any(key in cell for key in ("evidence_id", "estimate_id", "point_x")):
                errors.append("closed 8K cell must not carry performance evidence")

    packet = next(
        (item for item in family.get("packets", []) if item.get("id") == closure.get("packet_id")),
        None,
    )
    if packet is None:
        errors.append("closed graph packet is missing")
    elif "featured_metric" in packet or "no measured speed" not in packet.get("coverage", []):
        errors.append("closed graph packet must be speedless")

    family_closure = next(
        (item for item in family.get("family_closures", [])
         if item.get("evidence") == source.get("path")),
        None,
    )
    if family_closure is None or family_closure.get("state") != "closed":
        errors.append("exact graph family closure is missing")
    elif family_closure.get("selectors", {}).get("active_context_tokens") != 8192:
        errors.append("graph family closure is broader than exact 8K")

    serialized = json.dumps(family, sort_keys=True)
    for value in adjudication.get("protected_decode_values", []):
        if str(value) not in serialized:
            errors.append(f"protected decode value disappeared: {value}")
    return errors


def main() -> int:
    errors = validate(load_json(FAMILY_PATH), load_json(ADJUDICATION_PATH))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: 14 estimates retired behind measured rules; exact 8K graph/Q8-KV cell closed without speed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
