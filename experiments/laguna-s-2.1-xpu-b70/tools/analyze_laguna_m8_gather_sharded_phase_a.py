#!/usr/bin/env python3
"""Independent, host-only Phase-A aggregate recomputation.

This consumes the four sealed card results after all child processes have
exited.  It never imports the runtime, native libraries, or Torch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import run_laguna_m8_gather_sharded_phase_a as phase_a


FORMAT = "laguna-m8-gather-sharded-phase-a-aggregate-v3"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _read(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    return phase_a.read_canonical_json(path, label, 128 * 1024 * 1024)


def _read_sealed_child(root: Path, name: str, label: str) -> tuple[dict[str, Any], bytes]:
    """Read immutable child evidence through a retained parent descriptor."""
    root_fd, root_meta = phase_a._open_dir(root, f"{label} root")
    try:
        require(stat.S_IMODE(root_meta.st_mode) == 0o555, f"{label} root not sealed")
        descriptor, before = phase_a._open_at(root_fd, name, label)
        try:
            require(stat.S_IMODE(before.st_mode) == 0o444 and before.st_size <= 128 * 1024 * 1024, f"{label} not sealed")
            raw = os.pread(descriptor, before.st_size, 0)
            after = os.fstat(descriptor)
            require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} changed while reading")
        finally:
            os.close(descriptor)
    finally:
        os.close(root_fd)
    value = json.loads(raw, object_pairs_hook=phase_a._strict_object)
    require(isinstance(value, dict) and raw == phase_a.canonical_json(value), f"{label} canonical JSON")
    return value, raw


def _epoch_projection(row: dict[str, Any]) -> dict[str, Any]:
    """The raw exactness facts that must be identical on all physical cards."""
    return {key: row[key] for key in ("epoch", "input_before", "input_after", "outputs",
                                      "raw_bf16_classification", "comparisons", "passed")}


def _read_at(directory_fd: int, name: str, label: str) -> tuple[dict[str, Any], bytes]:
    descriptor, before = phase_a._open_at(directory_fd, name, label)
    try:
        require(stat.S_IMODE(before.st_mode) == 0o444, f"{label} not immutable")
        raw = os.pread(descriptor, before.st_size, 0)
        after = os.fstat(descriptor)
        require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} changed")
    finally:
        os.close(descriptor)
    value = json.loads(raw, object_pairs_hook=phase_a._strict_object)
    require(isinstance(value, dict) and raw == phase_a.canonical_json(value), f"{label} canonical JSON")
    return value, raw


def validate(packet_path: Path, packet_sha256: str, paths: list[Path],
             campaign_start: dict[str, str], campaign_fd: int) -> dict[str, Any]:
    packet, packet_raw = _read(packet_path, "Phase-A authorization")
    require(phase_a.sha_bytes(packet_raw) == packet_sha256, "Phase-A packet SHA")
    phase_a.validate_phase_a_packet(packet, packet_path, verify_artifacts=True)
    phase_a.verify_mutual_packets(packet)
    require(isinstance(campaign_start, dict) and set(campaign_start) == {"path", "sha256"} and
            campaign_start["path"] == str(Path(packet["body"]["aggregate_path"]).parent / "campaign-start.json") and
            phase_a._is_sha256(campaign_start["sha256"]), "campaign-start identity")
    start, start_raw = _read_at(campaign_fd, "campaign-start.json", "campaign start")
    require(hashlib.sha256(start_raw).hexdigest() == campaign_start["sha256"] and
            start.get("format") == "laguna-m8-gather-sharded-phase-a-start-v4" and
            start.get("packet_path") == str(packet_path) and start.get("packet_sha256") == packet_sha256 and
            start.get("one_shot") is True, "campaign-start binding")
    require(len(paths) == 4, "exactly four card result paths")
    results: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for rank, path in enumerate(paths):
        expected = Path(packet["body"]["cards"][rank]["output_root"]) / "evidence/component-result.json"
        require(path == expected, f"card{rank} result path")
        phase_a.assert_live_internal_nvme(path.parent, f"card{rank} result root")
        result, raw = _read_sealed_child(path.parent, "component-result.json", f"card{rank} result")
        phase_a.validate_card_result(result, packet, rank)
        results.append(result)
        entries.append({"rank": rank, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
    canonical_epochs: list[dict[str, Any]] = []
    for phase, field in (("pre", "pre_epochs"), ("post", "post_epochs")):
        for index in range(len(results[0][field])):
            first = _epoch_projection(results[0][field][index])
            for rank, result in enumerate(results[1:], 1):
                require(_epoch_projection(result[field][index]) == first,
                        f"cross-card {phase} epoch raw/output/classification mismatch: card{rank}/{index}")
            canonical_epochs.append({"phase": phase, **first})
    cards = []
    for result in results:
        timing = result["timing"]
        cards.append({"rank": result["rank"], "candidate_block_wins": timing["candidate_block_wins"],
                      "median_saving_ms_per_cycle": timing["median_saving_ms_per_cycle"],
                      "thresholds_passed": True, "exactness_passed": True})
    return {"format": FORMAT, "status": "component_timing_pass_pending_mandatory_counters", "passed": True,
            "packet_path": str(packet_path), "packet_sha256": packet_sha256, "card_results": entries,
            "cards": cards, "all_cards_required": True, "cross_card_epoch_record_sha256": hashlib.sha256(
                phase_a.canonical_json(canonical_epochs)).hexdigest(), "phase_b_required": True,
            "campaign_root": str(Path(packet["body"]["aggregate_path"]).parent),
            "campaign_start": campaign_start,
            "campaign_terminal_path": str(Path(packet["body"]["aggregate_path"]).parent / "campaign-terminal.json"),
            "campaign_terminal_format": "laguna-m8-gather-sharded-phase-a-campaign-terminal-v3",
            "phase_b_authorizer_requirements": {"terminal_mode": 0o444, "campaign_mode": 0o555,
                "phase_b_authorized": True, "terminal_must_bind_this_aggregate_sha256": True,
                "terminal_must_bind_campaign_start_sha256": campaign_start["sha256"]},
            "endpoint_authorized": False, "model_generation_authorized": False, "submission_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument("--expected-authorization-sha256", required=True)
    parser.add_argument("--card-result", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    campaign_fd = os.open(args.out.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        report = validate(args.authorization_json, args.expected_authorization_sha256, args.card_result,
                          {"path": str(args.out.parent / "campaign-start.json"),
                           "sha256": phase_a.sha256_file(args.out.parent / "campaign-start.json", "campaign start")},
                          campaign_fd)
        require(args.out.is_absolute() and "/" not in args.out.name, "aggregate output path")
        phase_a._write_exclusive_at(campaign_fd, args.out.name, report)
    finally:
        os.close(campaign_fd)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
