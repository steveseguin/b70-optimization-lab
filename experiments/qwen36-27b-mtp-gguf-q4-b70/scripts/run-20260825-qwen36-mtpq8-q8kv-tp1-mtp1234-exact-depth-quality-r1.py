#!/usr/bin/env python3
"""Q8-KV MTP1/2/3/4 full expansion, mechanically overlaid on F16 R1."""

from __future__ import annotations

import hashlib, json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1-prereg.json"
F16_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
CAMPAIGN_ID = "qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-20260825-r1"
RUN_ROOT = "/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024): digest.update(block)
    return digest.hexdigest()


def validate_overlay(value: dict[str, Any]) -> None:
    s, e, l, f = value.get("selectors") or {}, value.get("execution_contract") or {}, value.get("lifecycle") or {}, value.get("frozen_interpretation") or {}
    if not (value.get("schema") == "neural.download.qwen36-llama-mtp1234-q8kv-exact-depth-quality-prereg.v1" and value.get("campaign_id") == CAMPAIGN_ID and value.get("state") == "preregistered-not-launched" and s.get("candidate_mtp") == [1, 2, 3, 4] and s.get("control_mtp") == 0 and s.get("active_context_tokens") == [0, 2048, 4096, 8192, 16384, 24576, 32768] and s.get("target_kv") == s.get("draft_kv") == "q8_0" and s.get("graph_mode") == "off" and e.get("arm_order") == ["control-mtp0", "candidate-mtp1", "candidate-mtp2", "candidate-mtp3", "candidate-mtp4"] and e.get("quality_battery_per_candidate") is True and e.get("candidate_failure_is_route_local") is True and e.get("control_failure_invalidates_all") is True and l.get("output_root") == RUN_ROOT and l.get("exact_ack") == ACK and l.get("default_is_inert") is True and f.get("site_publication_authorized") is False and f.get("graph_claim_authorized") is False and f.get("headline_or_protected_replacement_authorized") is False):
        raise RuntimeError("Q8-KV full-expansion overlay invariant failed")


def load_overlay() -> dict[str, Any]:
    value = json.loads(OVERLAY.read_text(encoding="utf-8")); validate_overlay(value); return value


def verify_parents(value: dict[str, Any]) -> None:
    f16, route = value["parents"]["sealed_mtp3_r3_result"], value["parents"]["route_screen_r2"]
    for raw, expected in ((f16["path"], f16["sha256"]), (f16["raw_terminal"], f16["raw_terminal_sha256"]), (route["manifest"], route["manifest_sha256"]), (route["runner"], route["runner_sha256"]), (route["validator"], route["validator_sha256"]), (route["raw_terminal"], route["raw_terminal_sha256"])):
        path = Path(raw) if Path(raw).is_absolute() else REPO / raw
        if not path.is_file() or sha256_file(path) != expected: raise RuntimeError(f"parent changed: {path}")
    f16_result = TRANSFORMED.CORE.load_json(REPO / f16["path"]); f16_terminal = TRANSFORMED.CORE.load_json(Path(f16["raw_terminal"])); route_terminal = TRANSFORMED.CORE.load_json(Path(route["raw_terminal"]))
    control_hashes = {str(cell["active_context_tokens"]): cell["receipt"].get("output_token_ids_sha256") for arm in f16_terminal.get("arms", []) if arm.get("mtp") == 0 for cell in arm.get("cells", [])}
    if not (f16_result.get("classification") == "quality-battery-certified-family-research-profile" and f16_terminal.get("status") == f16["required_status"] and f16_terminal.get("authority", {}).get("candidate_routes_with_seven_quality-complete_cells_if_reviewed") == f16["required_routes"] and control_hashes == value["sealed_target_output_hashes"] and route_terminal.get("status") == route["required_status"] and route_terminal.get("screen_gate", {}).get("passed") is True and route_terminal.get("authority", {}).get("routes_eligible_for_separately_preregistered_q8kv_curve") == route["required_eligible_routes"]):
        raise RuntimeError("parent result invariant failed")


def transformed_source() -> str:
    source = F16_RUNNER.read_text(encoding="utf-8")
    replacements = (
        ("qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1", CAMPAIGN_ID, 2),
        ("2026-08-25-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1-prereg.json", OVERLAY.name, 1),
        ("validate-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py", "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1.py", 1),
        ("ROUTES = (0, 1, 2, 4)", "ROUTES = (0, 1, 2, 3, 4)", 1),
        ('ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 4: "candidate-mtp4"}', 'ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 3: "candidate-mtp3", 4: "candidate-mtp4"}', 1),
        ('class Execution(BASE.Execution):\n    pass', 'class Execution(BASE.Execution):\n    def server_argv_for_mtp(self, mtp: int) -> list[str]:\n        argv = super().server_argv_for_mtp(mtp)\n        for flag in ("-ctk", "-ctv"):\n            argv[argv.index(flag) + 1] = "q8_0"\n        if mtp > 0:\n            for flag in ("--spec-draft-type-k", "--spec-draft-type-v"):\n                argv[argv.index(flag) + 1] = "q8_0"\n        return argv', 1),
        ("neural.download.qwen36-llama-mtp124-exact-depth-quality", "neural.download.qwen36-llama-mtp1234-q8kv-exact-depth-quality", 3),
        ('"fresh_server_lifetimes": 4', '"fresh_server_lifetimes": 5', 1),
        ('"candidate_quality_batteries": 3', '"candidate_quality_batteries": 4', 1),
    )
    for old, new, expected in replacements:
        count = source.count(old)
        if count != expected: raise RuntimeError(f"transform count drift {old!r}: {count}")
        source = source.replace(old, new)
    return source


source = transformed_source(); TRANSFORMED = ModuleType("qwen36_q8kv_mtp1234_expansion_transformed"); TRANSFORMED.__file__ = str(F16_RUNNER); TRANSFORMED.__package__ = None; sys.modules[TRANSFORMED.__name__] = TRANSFORMED; exec(compile(source, str(F16_RUNNER), "exec"), TRANSFORMED.__dict__)
TRANSFORMED.load_overlay = load_overlay; TRANSFORMED.validate_overlay = validate_overlay; TRANSFORMED.verify_parents = verify_parents
TRANSFORMED_SOURCE_SHA256 = hashlib.sha256(source.encode()).hexdigest()
BASE = TRANSFORMED.BASE; CORE = TRANSFORMED.CORE; ROUTE_R2 = TRANSFORMED.ROUTE_R2; ROUTES = TRANSFORMED.ROUTES; ARMS = TRANSFORMED.ARMS; DEPTHS = TRANSFORMED.DEPTHS; Execution = TRANSFORMED.Execution; merged_manifest = TRANSFORMED.merged_manifest; static_check = TRANSFORMED.static_check; execute = TRANSFORMED.execute


def main() -> int:
    verify_parents(load_overlay())
    return TRANSFORMED.main()


if __name__ == "__main__": raise SystemExit(main())
