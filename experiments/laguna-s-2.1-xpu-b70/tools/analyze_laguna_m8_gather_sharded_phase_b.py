#!/usr/bin/env python3
"""Offline, per-card-only analyzer for the M8 sharded-gather Phase-B capture."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from statistics import fmean
from typing import Any

import laguna_m8_gather_sharded_counter_parser as counters
import run_laguna_m8_gather_sharded_phase_b as runner
import run_laguna_m8_gather_sharded_phase_a as phase_a

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def _regular_bytes(path: Path, maximum: int = 512 * 1024 * 1024) -> tuple[bytes, os.stat_result]:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= maximum, f"unsafe retained evidence: {path}")
        raw = bytearray()
        while len(raw) < before.st_size:
            block = os.read(descriptor, min(1024 * 1024, before.st_size - len(raw)))
            require(bool(block), f"short retained evidence read: {path}")
            raw.extend(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f"evidence changed during retained read: {path}")
    return bytes(raw), before

def sha(path: Path) -> str:
    return hashlib.sha256(_regular_bytes(path)[0]).hexdigest()

def read(path: Path, expected: str | None = None) -> dict[str, Any]:
    require(path.is_absolute() and not path.is_symlink(), f"unsafe evidence: {path}")
    raw, _metadata = _regular_bytes(path, 128 * 1024 * 1024)
    if expected is not None:
        require(hashlib.sha256(raw).hexdigest() == expected, f"hash drift: {path}")
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", f"noncanonical JSON: {path}")
    return value

def _entry(base: Path, value: object, name: str) -> Path:
    require(isinstance(value, dict) and set(value) == {"path", "sha256", "bytes"}, f"file entry schema: {name}")
    path = base / name
    raw, metadata = _regular_bytes(path)
    require(not path.is_symlink() and path.resolve(strict=True) == path and value["path"] == str(path) and isinstance(value["bytes"], int) and value["bytes"] > 0 and hashlib.sha256(raw).hexdigest() == value["sha256"] and metadata.st_size == value["bytes"], f"file entry drift: {name}")
    return path

def validate_output_evidence(value: object, phase_rows: list[dict[str, Any]], treatment: str) -> list[dict[str, Any]]:
    """Bind every captured repeat to the corresponding canonical Phase-A bits."""
    require(treatment in {"control", "candidate"} and len(phase_rows) >= counters.LAYERS, "invalid exactness treatment/reference")
    require(isinstance(value, list) and len(value) == counters.RAW_ROWS, "must retain all 13x47 raw output records")
    key = "control_gather" if treatment == "control" else "candidate_gather"
    validated: list[dict[str, Any]] = []
    for ordinal, row in enumerate(value):
        cycle, layer = divmod(ordinal, counters.LAYERS)
        expected = phase_rows[layer]
        require(isinstance(row, dict) and set(row) == {"cycle", "layer", "raw_bf16_le_sha256", "classification"} and row["cycle"] == cycle and row["layer"] == layer and row["raw_bf16_le_sha256"] == expected["outputs"][key] and row["classification"] == expected["raw_bf16_classification"], f"raw Phase-B output differs from canonical Phase-A: cycle{cycle}/layer{layer}")
        validated.append(row)
    return validated


def validate_input_integrity(value: object, fixture_binding: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "route_rows": fixture_binding["records"]["route_rows"]["per_epoch_sha256"][:counters.LAYERS],
        "weights": fixture_binding["records"]["weights"]["per_epoch_sha256"][:counters.LAYERS],
        "canonical_route_map": fixture_binding["canonical_route_map"]["sha256"],
    }
    require(isinstance(value, dict) and set(value) == {"before", "after", "passed"} and value["passed"] is True and value["before"] == expected and value["after"] == expected, "route/weight/map input immutability drift")
    return value


def validate_operational_sample(value: object) -> dict[str, Any]:
    return runner.validate_operational_sample(value)


def decide_card_counters(arm_means: dict[str, dict[str, float]]) -> dict[str, Any]:
    require(set(arm_means) == set(counters.ARMS), "card arm means schema")
    pairs = []
    for control_arm, candidate_arm in (("A1", "B1"), ("A2", "B2")):
        decision = counters.compare({"means": arm_means[control_arm]}, {"means": arm_means[candidate_arm]})
        pairs.append({"control_arm": control_arm, "candidate_arm": candidate_arm, "control": {"means": arm_means[control_arm]}, "candidate": {"means": arm_means[candidate_arm]}, "decision": decision})
    aggregate_control = {"means": {field: fmean((arm_means["A1"][field], arm_means["A2"][field])) for field in counters.MEAN_FIELDS}}
    aggregate_candidate = {"means": {field: fmean((arm_means["B1"][field], arm_means["B2"][field])) for field in counters.MEAN_FIELDS}}
    aggregate_decision = counters.compare(aggregate_control, aggregate_candidate)
    return {"matched_pairs": pairs, "aggregate": {"control": aggregate_control, "candidate": aggregate_candidate, "decision": aggregate_decision}, "passed": all(pair["decision"]["passed"] is True for pair in pairs) and aggregate_decision["passed"] is True}


def analyze(packet_path: Path, packet_sha: str, aggregate_path: Path, aggregate_sha: str, capture_path: Path) -> dict[str, Any]:
    packet, aggregate, capture = read(packet_path, packet_sha), read(aggregate_path, aggregate_sha), read(capture_path)
    authorization = runner.validate(packet, packet_path, packet_sha, aggregate, aggregate_path, aggregate_sha)
    body, common = authorization["body"], authorization["common"]
    phase_a_packet = read(Path(body["phase_a_binding"]["authorization_path"]))
    phase_results: list[dict[str, Any]] = []
    for rank, entry in enumerate(aggregate["card_results"]):
        result, result_sha = runner._read_unbound(Path(entry["path"]), f"Phase-A card{rank} result")
        require(result_sha == entry["sha256"], "Phase-A card result changed before Phase-B analysis")
        phase_results.append(phase_a.validate_card_result(result, phase_a_packet, rank))
    root = Path(body["output_root"])
    require(set(capture) == {"format", "status", "packet_sha256", "phase_a_aggregate_sha256", "phase_a_predecessor", "boot_id", "storage", "post_arm_idle_preflight", "arms"}, "capture schema drift")
    require(capture_path == root / "capture.json" and capture.get("format") == "laguna-m8-gather-sharded-phase-b-capture-v3" and capture.get("status") == "complete_pending_mandatory_in_process_analysis" and capture.get("packet_sha256") == packet_sha and capture.get("phase_a_aggregate_sha256") == aggregate_sha, "capture identity/root drift")
    require(capture["phase_a_predecessor"] == authorization["phase_a_predecessor"], "capture predecessor authorization drift")
    require(capture["storage"] == common["native_bundle"]["storage"], "capture is not bound to frozen internal NVMe")
    final = capture.get("post_arm_idle_preflight")
    require(isinstance(final, dict) and set(final) == {"path", "sha256"} and final["path"] == str(root / "post-arm-idle-preflight.json"), "final-idle path schema drift")
    post_idle = read(Path(final["path"]), final["sha256"])
    validate_operational_sample(post_idle)
    listed = capture.get("arms")
    require(isinstance(listed, list) and len(listed) == 16, "must have exactly four cards x A1/B1/B2/A2")
    records: dict[tuple[int, str], dict[str, Any]] = {}
    boot_ids: set[str] = set()
    expected_order = [(rank, arm) for rank in range(4) for arm in counters.ARMS]
    for ordinal, item in enumerate(listed):
        require(isinstance(item, dict) and set(item) == {"ordinal", "rank", "arm", "manifest"} and item["ordinal"] == ordinal and (item["rank"], item["arm"]) == expected_order[ordinal], "capture chronological arm listing drift")
        key = (item["rank"], item["arm"])
        require(key not in records, "duplicate arm")
        manifest_path = Path(item["manifest"])
        expected_root = root / f"card{key[0]}" / key[1]
        require(manifest_path == expected_root / "manifest.json", "arm path drift")
        manifest = read(manifest_path)
        require(set(manifest) == {"format", "status", "rank", "arm", "packet_sha256", "phase_a_aggregate_sha256", "command", "environment", "session", "unitrace_launch", "tool_stage", "unitrace_returncode", "normal_return_metric_flush_closed", "initial_start_paused_acknowledged", "fixture", "files"}, "arm manifest schema drift")
        phase_card = body["cards"][key[0]]
        arm_environment = phase_card["environments"][key[1]]
        require(manifest.get("format") == "laguna-m8-gather-sharded-phase-b-arm-v3" and manifest.get("status") == "complete" and manifest.get("rank") == key[0] and manifest.get("arm") == key[1] and manifest.get("packet_sha256") == packet_sha and manifest.get("phase_a_aggregate_sha256") == aggregate_sha and manifest.get("environment") == arm_environment and manifest.get("session") == phase_card["sessions"][key[1]] and manifest.get("unitrace_returncode") == 0 and manifest.get("normal_return_metric_flush_closed") is True and manifest.get("initial_start_paused_acknowledged") is True, "arm manifest binding drift")
        expected_source_identities = {
            "phase_b": body["tools"],
            "phase_a": {
                "runner": phase_a_packet["body"]["runner"],
                "analyzer": phase_a_packet["body"]["analyzer"],
            },
        }
        tool_stage = manifest["tool_stage"]
        require(isinstance(tool_stage, dict) and set(tool_stage) == {"before", "after", "retained_through_child_exit"} and tool_stage["retained_through_child_exit"] is True and tool_stage["before"] == tool_stage["after"], "retained tool-stage closure drift")
        stage_record = tool_stage["before"]
        require(isinstance(stage_record, dict) and set(stage_record) == {"format", "path", "source_identities", "staged_files", "retained_files", "directory_mode"} and stage_record["format"] == "laguna-m8-gather-sharded-phase-b-retained-tool-stage-v1" and stage_record["path"] == str(expected_root / "tool-stage") and stage_record["source_identities"] == expected_source_identities and stage_record["directory_mode"] == 0o555, "tool-stage identity/root drift")
        stage_path = Path(stage_record["path"])
        stage_metadata = os.stat(stage_path, follow_symlinks=False)
        require(stat.S_ISDIR(stage_metadata.st_mode) and stat.S_IMODE(stage_metadata.st_mode) == 0o555 and not stage_path.is_symlink(), "tool-stage directory is not sealed")
        closure = read(stage_path / "tool-closure.json")
        require(closure == {"format": "laguna-m8-gather-sharded-phase-b-tool-closure-v1", "source_identities": expected_source_identities, "staged_files": stage_record["staged_files"]}, "tool-stage closure manifest drift")
        retained_files = stage_record["retained_files"]
        expected_names = {name for mapping in stage_record["staged_files"].values() for name in mapping.values()} | {"tool-closure.json"}
        require(isinstance(retained_files, dict) and set(retained_files) == expected_names, "tool-stage retained inventory drift")
        for name, retained in retained_files.items():
            raw_stage, metadata_stage = _regular_bytes(stage_path / name, 8 * 1024 * 1024)
            require(isinstance(retained, dict) and set(retained) == {"sha256", "dev", "inode", "bytes", "mode"} and retained["sha256"] == hashlib.sha256(raw_stage).hexdigest() and retained["dev"] == metadata_stage.st_dev and retained["inode"] == metadata_stage.st_ino and retained["bytes"] == metadata_stage.st_size and retained["mode"] == stat.S_IMODE(metadata_stage.st_mode) == 0o444, f"tool-stage retained file drift: {name}")
        unitrace_launch = manifest["unitrace_launch"]
        require(isinstance(unitrace_launch, dict) and set(unitrace_launch) == {"configured_path", "exec_path", "sha256", "dev", "inode", "bytes", "mode", "retained_through_child_exit"} and unitrace_launch["configured_path"] == str(runner.UNITRACE) and re.fullmatch(r"/proc/[1-9][0-9]*/fd/[0-9]+", unitrace_launch["exec_path"] or "") is not None and unitrace_launch["sha256"] == runner.UNITRACE_SHA256 and unitrace_launch["retained_through_child_exit"] is True and isinstance(unitrace_launch["dev"], int) and isinstance(unitrace_launch["inode"], int) and isinstance(unitrace_launch["bytes"], int) and unitrace_launch["bytes"] > 0 and unitrace_launch["mode"] == 0o755, "retained unitrace launch closure drift")
        files = manifest.get("files")
        require(isinstance(files, dict) and set(files) == {"fixture.json", "unitrace." + str(manifest["fixture"]["pid"]), "unitrace.metrics." + str(manifest["fixture"]["pid"]), "current-idle-preflight.json", "runtime-prelaunch.json", "session-prelaunch.json", "session-poststop.json", "process-terminal.json", "stdout.log", "stderr.log"}, "two unitrace PID output/session closure drift")
        timing_name = "unitrace." + str(manifest["fixture"]["pid"])
        metrics_name = "unitrace.metrics." + str(manifest["fixture"]["pid"])
        idle = read(_entry(expected_root, files["current-idle-preflight.json"], "current-idle-preflight.json"))
        require(isinstance(idle, dict) and set(idle) == {"format", "status", "started_utc", "ended_utc", "duration_required_seconds", "sample_interval_seconds", "minimum_samples", "elapsed_seconds", "boot_id_before", "boot_id_after", "samples"} and idle["format"] == "laguna-m8-gather-sharded-phase-b-continuous-idle-v1" and idle["status"] == "passed" and idle["duration_required_seconds"] == 65 and idle["sample_interval_seconds"] == 5 and idle["minimum_samples"] == 14 and isinstance(idle["elapsed_seconds"], (int, float)) and idle["elapsed_seconds"] >= 65 and idle["boot_id_before"] == idle["boot_id_after"], "arm continuous-idle contract drift")
        idle_samples = idle["samples"]
        require(isinstance(idle_samples, list) and len(idle_samples) >= 14, "arm strict-idle samples missing")
        prior_elapsed = -1.0
        for ordinal, sample in enumerate(idle_samples):
            require(isinstance(sample, dict) and set(sample) == {"ordinal", "elapsed_seconds", "report"} and sample["ordinal"] == ordinal and isinstance(sample["elapsed_seconds"], (int, float)) and sample["elapsed_seconds"] >= prior_elapsed, "arm strict-idle sample chronology drift")
            validate_operational_sample(sample["report"])
            prior_elapsed = float(sample["elapsed_seconds"])
        require(prior_elapsed <= idle["elapsed_seconds"], "arm strict-idle elapsed closure drift")
        boot_ids.add(idle["boot_id_before"])
        runtime_prelaunch = read(_entry(expected_root, files["runtime-prelaunch.json"], "runtime-prelaunch.json"))
        require(runtime_prelaunch.get("format") == "laguna-m8-gather-sharded-phase-b-runtime-prelaunch-v1" and runtime_prelaunch.get("rank") == key[0] and runtime_prelaunch.get("arm") == key[1] and runtime_prelaunch.get("arm_root") == str(expected_root) and runtime_prelaunch.get("fresh") is True, "fresh arm runtime proof drift")
        session = phase_card["sessions"][key[1]]
        shm_path = str(runner._session_path(session))
        pre_session = read(_entry(expected_root, files["session-prelaunch.json"], "session-prelaunch.json"))
        post_session = read(_entry(expected_root, files["session-poststop.json"], "session-poststop.json"))
        require(set(pre_session) == {"format", "session", "shm_path", "absent", "checked_utc"} and set(post_session) == {"format", "session", "shm_path", "absent", "checked_utc"}, "session evidence schema drift")
        require(pre_session.get("format") == "laguna-m8-gather-sharded-phase-b-session-prelaunch-v1" and pre_session.get("session") == session and pre_session.get("shm_path") == shm_path and pre_session.get("absent") is True, "session prelaunch absence proof drift")
        require(post_session.get("format") == "laguna-m8-gather-sharded-phase-b-session-poststop-v1" and post_session.get("session") == session and post_session.get("shm_path") == shm_path and post_session.get("absent") is True, "session post-stop unlink proof drift")
        process_terminal = read(_entry(expected_root, files["process-terminal.json"], "process-terminal.json"))
        require(process_terminal == {"format": "laguna-m8-gather-sharded-phase-b-process-terminal-v1", "process_started": True, "pid": process_terminal.get("pid"), "returncode": 0, "reaped": True, "process_group_dead": True, "timed_out": False, "error_type": None, "error_message": None, "termination": [], "stdout_sha256": files["stdout.log"]["sha256"], "stderr_sha256": files["stderr.log"]["sha256"]} and isinstance(process_terminal["pid"], int) and process_terminal["pid"] > 0, "unitrace process terminal drift")
        stdout_path = _entry(expected_root, files["stdout.log"], "stdout.log")
        stderr_path = _entry(expected_root, files["stderr.log"], "stderr.log")
        stderr = _regular_bytes(stderr_path)[0]
        require(stderr.count(f"[INFO] Session {session} is paused\n".encode()) == 1 and b"was not stopped before reusing" not in stderr, "initial start-paused acknowledgement/reuse evidence drift")
        fixture_path = _entry(expected_root, files["fixture.json"], "fixture.json")
        require(stat.S_IMODE(_regular_bytes(fixture_path)[1].st_mode) == runner.fixture.FIXTURE_OUTPUT_MODE, "fixture evidence mode drift")
        fixture_record = read(fixture_path, files["fixture.json"]["sha256"])
        require(set(fixture_record) == {"format", "status", "pid", "rank", "arm", "packet_sha256", "phase_a_aggregate_sha256", "selected_kernel", "cycles", "layers_per_cycle", "selected_gather_calls", "epoch_range", "capture_scope", "runtime", "application_environment", "application_environment_sha256", "unitrace_mapping", "fixture_fd_validation", "native_closure", "input_integrity", "output_evidence", "session", "resume", "pause", "stop"}, "fixture result schema drift")
        require(fixture_record == manifest["fixture"], "embedded fixture differs from raw fixture.json")
        require(_regular_bytes(stdout_path)[0] == (json.dumps(fixture_record, sort_keys=True) + "\n").encode(), "fixture stdout differs from sealed result")
        timing, metrics = _entry(expected_root, files[timing_name], timing_name), _entry(expected_root, files[metrics_name], metrics_name)
        timing_report, metric_report = counters.parse_timing(timing, key[1]), counters.parse_metrics(metrics, key[1])
        require(timing_report["sha256"] == files[timing_name]["sha256"] and metric_report["sha256"] == files[metrics_name]["sha256"], "parsed profiler file changed after manifest binding")
        expected_command = runner.argv(packet_path, packet_sha, aggregate_path, aggregate_sha, key[0], key[1], fixture_path, arm_environment, session, stage_path, unitrace_launch["exec_path"])
        require(manifest.get("command") == expected_command, "captured command drift")
        physical = common["cards"][key[0]]
        counter_tools = body["counter_tools"]
        observed_environment = runner.fixture.validate_recorded_application_environment(fixture_record.get("application_environment"), key[0], expected_root, session, counter_tools["libunitrace_tool"]["path"], counter_tools["pti_commit"])
        require(fixture_record.get("application_environment_sha256") == hashlib.sha256(canonical(observed_environment) + b"\n").hexdigest(), "fixture application-environment digest drift")
        mapping = fixture_record.get("unitrace_mapping")
        require(isinstance(mapping, dict) and set(mapping) == {"path", "sha256", "mapped", "matching_map_entries"} and mapping["path"] == counter_tools["libunitrace_tool"]["path"] and mapping["sha256"] == counter_tools["libunitrace_tool"]["sha256"] and mapping["mapped"] is True and isinstance(mapping["matching_map_entries"], int) and mapping["matching_map_entries"] > 0, "fixture unitrace mapping closure drift")
        fixture_binding = common["fixture"]
        expected_fd_validation = {
            name: {"sha256": fixture_binding["records"][name]["sha256"], "per_epoch_sha256": fixture_binding["records"][name]["per_epoch_sha256"]}
            for name in ("route_rows", "weights")
        }
        expected_fd_validation["canonical_route_map"] = {"sha256": fixture_binding["canonical_route_map"]["sha256"], "bytes": 320}
        require(fixture_record.get("fixture_fd_validation") == {"before": expected_fd_validation, "after": expected_fd_validation, "retained_through_stop": True}, "fixture retained-descriptor evidence drift")
        native = fixture_record.get("native_closure")
        require(isinstance(native, dict) and set(native) == {"load", "before", "after", "retained_through_stop"} and native["retained_through_stop"] is True and native["before"] == native["after"], "native retained closure drift")
        bundle_libraries = common["native_bundle"]["libraries"]
        require(isinstance(native["before"], dict) and set(native["before"]) == set(bundle_libraries), "native retained inventory drift")
        for name, retained in native["before"].items():
            expected_library = bundle_libraries[name]
            require(isinstance(retained, dict) and set(retained) == {"sha256", "dev", "inode", "bytes", "mode"} and retained["sha256"] == expected_library["sha256"] and retained["bytes"] == expected_library["bytes"] and retained["mode"] == 0o444 and isinstance(retained["dev"], int) and isinstance(retained["inode"], int), f"native retained identity drift: {name}")
        load = native["load"]
        require(isinstance(load, dict) and set(load) == {"libraries", "same_basename_extras", "all_eight_mapped"} and load["same_basename_extras"] is False and load["all_eight_mapped"] is True and isinstance(load["libraries"], dict) and set(load["libraries"]) == set(bundle_libraries), "native mapping closure drift")
        require(all(isinstance(value, dict) and value.get("sha256") == bundle_libraries[name]["sha256"] and value.get("mapping_verified") is True and isinstance(value.get("mapping_segments"), int) and value["mapping_segments"] > 0 for name, value in load["libraries"].items()), "native mapped-library identity drift")
        input_integrity = validate_input_integrity(fixture_record.get("input_integrity"), fixture_binding)
        output_evidence = validate_output_evidence(fixture_record.get("output_evidence"), phase_results[key[0]]["pre_epochs"], counters.ARMS[key[1]])
        runtime = fixture_record.get("runtime")
        require(isinstance(runtime, dict) and set(runtime) == {"visible_device_count", "current_device", "logical_device", "device_name", "xpu_smi_uuid", "runtime_uuid_bytes_hex", "torch_runtime_uuid", "torch_runtime_uuid_bytes_hex", "runtime_uuid_mapping", "bdf", "drm_card", "pci_vendor", "pci_device"}, "fixture runtime-card schema drift")
        require(isinstance(runtime, dict) and runtime.get("visible_device_count") == 1 and runtime.get("current_device") == 0 and runtime.get("logical_device") == "xpu:0" and runtime.get("device_name") == "Intel(R) Arc(TM) Pro B70 Graphics" and runtime.get("xpu_smi_uuid") == physical["xpu_smi_uuid"] and runtime.get("bdf") == physical["bdf"] and runtime.get("drm_card") == physical["drm_card"] and runtime.get("pci_vendor") == "0x8086" and runtime.get("pci_device") == "0xe223" and runtime.get("runtime_uuid_mapping") == "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes" and isinstance(runtime.get("runtime_uuid_bytes_hex"), str) and len(runtime["runtime_uuid_bytes_hex"]) == 32 and isinstance(runtime.get("torch_runtime_uuid"), str) and isinstance(runtime.get("torch_runtime_uuid_bytes_hex"), str) and len(runtime["torch_runtime_uuid_bytes_hex"]) == 32, "fixture runtime-card evidence drift")
        require(bytes.fromhex(runtime["torch_runtime_uuid_bytes_hex"])[::-1].hex() == runtime["runtime_uuid_bytes_hex"], "runtime UUID reverse-byte evidence drift")
        require(isinstance(fixture_record, dict) and fixture_record.get("format") == "laguna-m8-gather-sharded-phase-b-fixture-v3" and fixture_record.get("status") == "complete" and fixture_record.get("rank") == key[0] and fixture_record.get("arm") == key[1] and fixture_record.get("packet_sha256") == packet_sha and fixture_record.get("phase_a_aggregate_sha256") == aggregate_sha and fixture_record.get("selected_kernel") == counters.KERNELS[counters.ARMS[key[1]]] and fixture_record.get("cycles") == 13 and fixture_record.get("layers_per_cycle") == 47 and fixture_record.get("selected_gather_calls") == 611 and fixture_record.get("epoch_range") == [0, 46] and fixture_record.get("capture_scope") == "resume_then_only_13x47_selected_gathers_then_final_xpu_synchronize_then_pause_then_stop_unlink" and fixture_record.get("session") == session, "fixture schema/selected-call closure drift")
        for action in ("resume", "pause", "stop"):
            control = fixture_record.get(action)
            acknowledgement = f"[INFO] Session {session} is stopped and can no longer be paused or resumed\n" if action == "stop" else f"[INFO] Session {session} is {action}d\n"
            require(isinstance(control, dict) and set(control) == {"command", "executed_via_retained_fd", "retained_identity", "returncode", "expected_stderr_utf8", "stdout_base64", "stdout_sha256", "stderr_base64", "stderr_sha256"} and control["command"] == [str(runner.UNITRACE), f"--{action}", session] and control["executed_via_retained_fd"] is True and control["returncode"] == 0 and control["expected_stderr_utf8"] == acknowledgement, f"{action} temporal control closure drift")
            retained_control = control["retained_identity"]
            require(isinstance(retained_control, dict) and set(retained_control) == {"sha256", "dev", "inode", "bytes", "mode"} and retained_control["sha256"] == runner.UNITRACE_SHA256 and isinstance(retained_control["dev"], int) and isinstance(retained_control["inode"], int) and isinstance(retained_control["bytes"], int) and retained_control["bytes"] > 0 and retained_control["mode"] == 0o755, f"{action} retained unitrace identity drift")
            for stream in ("stdout", "stderr"):
                try:
                    raw_control = base64.b64decode(control[f"{stream}_base64"], validate=True)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(f"invalid {action} {stream} evidence") from exc
                require(hashlib.sha256(raw_control).hexdigest() == control[f"{stream}_sha256"], f"{action} {stream} digest drift")
            require(base64.b64decode(control["stdout_base64"], validate=True) == b"" and base64.b64decode(control["stderr_base64"], validate=True) == acknowledgement.encode(), f"{action} temporal acknowledgement bytes drift")
        records[key] = {"timing": timing_report, "metrics": metric_report, "input_integrity": input_integrity, "output_evidence": output_evidence}
    require(set(records) == {(rank, arm) for rank in range(4) for arm in counters.ARMS}, "missing arm")
    require(boot_ids == {capture["boot_id"]}, "Phase-B arms/capture crossed boot identities")
    cards: list[dict[str, Any]] = []
    cross_card_outputs: list[list[dict[str, Any]]] = []
    for rank in range(4):
        arm_means = {arm: records[(rank, arm)]["metrics"]["means"] for arm in counters.ARMS}
        counter_decision = decide_card_counters(arm_means)
        canonical_outputs = records[(rank, "A1")]["output_evidence"]
        require(all(records[(rank, arm)]["output_evidence"] == canonical_outputs for arm in counters.ARMS), f"card{rank} A1/B1/B2/A2 raw output/repeat mismatch")
        require(records[(rank, "B1")]["output_evidence"] == records[(rank, "B2")]["output_evidence"] and records[(rank, "A1")]["output_evidence"] == records[(rank, "A2")]["output_evidence"], f"card{rank} treatment repeat mismatch")
        cross_card_outputs.append(canonical_outputs)
        exactness = {
            "all_four_arms_raw_equal": True,
            "candidate_repeat_equal": True,
            "control_repeat_equal": True,
            "all_13_repeats_per_layer_equal": all(
                all(canonical_outputs[cycle * counters.LAYERS + layer] == canonical_outputs[layer] | {"cycle": cycle} for cycle in range(counters.RAW_CYCLES))
                for layer in range(counters.LAYERS)
            ),
            "output_evidence_sha256": hashlib.sha256(canonical(canonical_outputs) + b"\n").hexdigest(),
            "phase_a_reference": "pre_epochs[0:47]",
        }
        require(exactness["all_13_repeats_per_layer_equal"] is True, f"card{rank} within-arm repeat mismatch")
        cards.append({"rank": rank, "arms": {arm: {"means": arm_means[arm]} for arm in counters.ARMS}, "matched_pairs": counter_decision["matched_pairs"], "aggregate": counter_decision["aggregate"], "geometry": {"control": counters.GEOMETRY["control"], "candidate": counters.GEOMETRY["candidate"]}, "selected_calls_per_arm": 611, "retained_rows_per_arm": 517, "exactness": exactness, "passed": counter_decision["passed"]})
    require(all(value == cross_card_outputs[0] for value in cross_card_outputs[1:]), "cross-card Phase-B raw outputs differ")
    phase_projection = [{"layer": layer, "raw_bf16_le_sha256": phase_results[0]["pre_epochs"][layer]["outputs"]["control_gather"], "classification": phase_results[0]["pre_epochs"][layer]["raw_bf16_classification"]} for layer in range(counters.LAYERS)]
    phase_digest = hashlib.sha256(canonical(phase_projection) + b"\n").hexdigest()
    passed = all(card["passed"] is True for card in cards)
    return {"format": "laguna-m8-gather-sharded-phase-b-analysis-v3", "status": "component_counter_passed" if passed else "component_counter_failed_no_global_rescue", "passed": passed, "packet_path": str(packet_path), "packet_sha256": packet_sha, "phase_a_aggregate_path": str(aggregate_path), "phase_a_aggregate_sha256": aggregate_sha, "capture_path": str(capture_path), "counter_header": {"fields": 86, "sha256": counters.METRIC_HEADER_SHA256}, "cards": cards, "exactness": {"all_cards_raw_equal": True, "phase_a_canonical_47_digest": phase_digest, "phase_b_repeated_output_digest": cards[0]["exactness"]["output_evidence_sha256"]}, "matched_pair_count": 8, "card_aggregate_count": 4, "global_mean_used": False, "within_card_rescue_allowed": False, "endpoint_authorized": False}

def write(path: Path, value: dict[str, Any]) -> None:
    capture_root = Path(value["capture_path"]).parent
    require(path.is_absolute() and path.parent == capture_root and not path.exists() and path.parent.is_dir() and not path.parent.is_symlink(), "unsafe analysis output root")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        data = canonical(value) + b"\n"
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            require(count > 0, "short analysis write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--phase-a-aggregate", type=Path, required=True)
    parser.add_argument("--phase-a-aggregate-sha256", required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.packet, args.packet_sha256, args.phase_a_aggregate, args.phase_a_aggregate_sha256, args.capture)
    write(args.out, result)
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
