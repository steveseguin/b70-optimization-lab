"""CPU-only tamper, decision, and lifecycle tests for the counter analyzer."""

from __future__ import annotations

import hashlib
import json
import csv
from pathlib import Path

import pytest

import analyze_laguna_shared_gate_up_mm_counters as analyzer
import gate_laguna_shared_gate_up_mm_counters as gate


CONTROL_KERNEL = "gemm_kernel[SIMD16 {8; 1; 1} {128; 1; 1}]"
CANDIDATE_KERNEL = "gemm_kernel[SIMD16 {24; 1; 1} {128; 4; 1}]"
SHA = "a" * 64


def metric_mean(
    *,
    time: float,
    memory: float = 100.0,
    lsc: float = 100.0,
    active: float = 80.0,
    stall: float = 10.0,
    occupancy: float = 70.0,
) -> dict[str, float]:
    values = {field: 0.0 for field in analyzer.MEAN_FIELDS}
    values.update(
        {
            "GpuTime[ns]": time,
            "GPU_MEMORY_BYTE_READ[bytes]": memory,
            "LOAD_STORE_CACHE_BYTE_READ[bytes]": lsc,
            "XVE_ACTIVE[%]": active,
            "XVE_STALL[%]": stall,
            "XVE_THREADS_OCCUPANCY_ALL[%]": occupancy,
        }
    )
    return values


def profile(
    rank: int,
    arm: str,
    *,
    time: float = 90.0,
    memory: float = 100.0,
    lsc: float = 100.0,
    active: float = 80.0,
    stall: float = 10.0,
    occupancy: float = 70.0,
    salt: str = "same",
) -> dict:
    treatment = "control" if arm.startswith("A") else "candidate"
    kernel = CONTROL_KERNEL if treatment == "control" else CANDIDATE_KERNEL
    gate_hash = hashlib.sha256(f"{salt}:gate".encode()).hexdigest()
    up_hash = hashlib.sha256(f"{salt}:up".encode()).hexdigest()
    inputs = {
        "rows": hashlib.sha256(f"{salt}:rows".encode()).hexdigest(),
        "gate_weight": hashlib.sha256(f"{salt}:gw".encode()).hexdigest(),
        "up_weight": hashlib.sha256(f"{salt}:uw".encode()).hexdigest(),
    }
    inputs["combined"] = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    fixture = {
        "input_sha256": inputs,
        "input_fixture_sha256": inputs["combined"],
        "boundary_sha256": {"gate": gate_hash, "up": up_hash},
        "all_pair_output_sha256": [
            {"pair": str(index), "gate": gate_hash, "up": up_hash}
            for index in range(13)
        ],
    }
    mean = metric_mean(
        time=time,
        memory=memory,
        lsc=lsc,
        active=active,
        stall=stall,
        occupancy=occupancy,
    )
    return {
        "rank": rank,
        "arm": arm,
        "treatment": treatment,
        "manifest": {
            "path": f"/evidence/card{rank}/{arm}/manifest.json",
            "sha256": SHA,
        },
        "fixture": fixture,
        "metrics": {"kernel_name": kernel, "mean": mean},
        "timing": {
            "selected": {
                "kernel_name": kernel,
                "calls": 26,
                "time_ns": int(time * 26),
            }
        },
    }


def valid_profiles() -> list[dict]:
    rows = []
    for card in gate.CARDS:
        rank = card["rank"]
        rows += [
            profile(rank, "A1", time=100),
            profile(rank, "B1", time=90),
            profile(rank, "B2", time=91),
            profile(rank, "A2", time=100),
        ]
    return rows


def test_passing_profile_set() -> None:
    result = analyzer.analyze_profiles(valid_profiles())
    assert result["passed"] is True
    assert result["retained_pair_indices"] == list(range(2, 13))
    assert result["exactness"]["all_16_arms_raw_bit_exact"] is True
    assert result["global_four_card_candidate_vs_control"]["passed"] is True
    assert all(card["passed"] for card in result["cards"].values())


def test_no_global_rescue_for_matched_pair_loss() -> None:
    rows = valid_profiles()
    next(
        profile for profile in rows if profile["rank"] == 1 and profile["arm"] == "B1"
    )["metrics"]["mean"]["GpuTime[ns]"] = 101
    result = analyzer.analyze_profiles(rows)
    assert result["global_four_card_candidate_vs_control"]["passed"] is True
    assert result["cards"]["1"]["B1_vs_A1"]["passed"] is False
    assert result["cards"]["1"]["passed"] is False
    assert result["passed"] is False


def test_guardrail_threshold_is_fail_closed() -> None:
    rows = valid_profiles()
    for arm in ("B1", "B2"):
        candidate = next(
            profile
            for profile in rows
            if profile["rank"] == 2 and profile["arm"] == arm
        )
        candidate["metrics"]["mean"]["GPU_MEMORY_BYTE_READ[bytes]"] = 102.01
    result = analyzer.analyze_profiles(rows)
    aggregate = result["cards"]["2"]["candidate_vs_control_aggregate"]
    assert aggregate["checks"]["gpu_memory_read_regression_within_2pct"] is False
    assert result["passed"] is False


def test_cross_arm_output_or_kernel_tamper_is_rejected() -> None:
    rows = valid_profiles()
    rows[0]["fixture"]["boundary_sha256"]["gate"] = "0" * 64
    with pytest.raises(RuntimeError, match="raw input or gate/up output drift"):
        analyzer.analyze_profiles(rows)

    rows = valid_profiles()
    rows[0]["metrics"]["kernel_name"] = CANDIDATE_KERNEL
    with pytest.raises(RuntimeError, match="kernel identity"):
        analyzer.analyze_profiles(rows)


def device_record(rank: int) -> dict:
    unfiltered = {
        "device_list": [
            {
                "device_id": card["rank"],
                "uuid": card["uuid"],
                "pci_bdf_address": card["pci_bdf_address"],
                "drm_device": card["drm_device"],
                "device_name": card["device_name"],
            }
            for card in gate.CARDS
        ]
    }
    expected = gate.CARDS[rank]
    filtered = {
        "device_list": [
            {
                "device_id": 0,
                "uuid": expected["uuid"],
                "pci_bdf_address": expected["pci_bdf_address"],
                "drm_device": expected["drm_device"],
                "device_name": expected["device_name"],
            }
        ]
    }
    filtered_text = json.dumps(filtered)
    unfiltered_text = json.dumps(unfiltered)
    return {
        "rank": rank,
        "expected": expected,
        "filtered_text": filtered_text,
        "unfiltered_text": unfiltered_text,
        "filtered": filtered,
        "unfiltered": unfiltered,
        "uuid_bdf_binding_exact": True,
        "filtered_sha256": hashlib.sha256(filtered_text.encode()).hexdigest(),
        "unfiltered_sha256": hashlib.sha256(unfiltered_text.encode()).hexdigest(),
    }


def test_device_discovery_transcript_is_cryptographically_bound() -> None:
    record = device_record(2)
    assert analyzer.validate_device(record, 2, "synthetic device") == record
    record["filtered_text"] += " "
    with pytest.raises(RuntimeError, match="identity envelope drift"):
        analyzer.validate_device(record, 2, "synthetic device")


def test_evidence_inventory_excludes_only_private_runtime_and_final_self(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "card0" / "A1" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "cache").write_bytes(b"transient")
    (tmp_path / "analysis.json").write_bytes(b"analysis\n")
    (tmp_path / analyzer.FINAL_NAME).write_bytes(b"self\n")
    files, excluded = analyzer.evidence_inventory(tmp_path)
    assert set(files) == {"analysis.json"}
    assert excluded == ["card0/A1/runtime"]


def test_final_manifest_payload_rehashes_all_nonruntime_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / analyzer.ANALYSIS_NAME).write_bytes(b'{"x":1}\n')
    (tmp_path / analyzer.TERMINAL_NAME).write_bytes(b'{"y":1}\n')
    analysis = {
        "status": "counter-failed-stop-before-endpoint",
        "passed": False,
    }
    first = analyzer.final_manifest_payload(tmp_path, SHA, analysis)
    assert first["file_count"] == 2
    (tmp_path / analyzer.ANALYSIS_NAME).write_bytes(b'{"x":2}\n')
    second = analyzer.final_manifest_payload(tmp_path, SHA, analysis)
    assert first != second


def packet_for(root: Path) -> dict:
    return {
        "packet_path": "/home/steve/llm-optimizations/data/frozen.json",
        "campaign": {"root": str(root)},
    }


def test_analysis_error_seal_cannot_escape_authorized_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    authorized = runs / "shared-gate-up-m8-counters-20260724T120000Z"
    unrelated = tmp_path / "unrelated"
    authorized.mkdir()
    unrelated.mkdir()
    monkeypatch.setattr(analyzer.contract, "RUNS", runs)
    with pytest.raises(RuntimeError, match="outside the packet-authorized"):
        analyzer.maybe_seal_analysis_error(
            unrelated,
            packet_for(authorized),
            SHA,
            RuntimeError("synthetic"),
        )
    assert not (unrelated / "analysis.error.json").exists()


def test_corrupt_analysis_is_terminally_sealed_but_valid_analysis_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(analyzer.contract, "RUNS", runs)

    corrupt = runs / "shared-gate-up-m8-counters-20260724T120001Z"
    corrupt.mkdir()
    (corrupt / "campaign.complete.json").write_bytes(b"complete\n")
    (corrupt / analyzer.ANALYSIS_NAME).write_bytes(b'{"partial":')
    analyzer.maybe_seal_analysis_error(
        corrupt,
        packet_for(corrupt),
        SHA,
        RuntimeError("synthetic"),
    )
    sealed = analyzer.read_canonical(corrupt / "analysis.error.json", "analysis error")
    assert sealed["status"] == "counter-failed-stop-before-endpoint"
    assert sealed["observed_analysis"]["bytes"] > 0

    valid = runs / "shared-gate-up-m8-counters-20260724T120002Z"
    valid.mkdir()
    (valid / "campaign.complete.json").write_bytes(b"complete\n")
    analysis = {
        "format": "laguna-shared-gate-up-m8-counter-analysis-v2",
        "campaign_root": str(valid),
        "authorization_sha256": SHA,
    }
    (valid / analyzer.ANALYSIS_NAME).write_bytes(analyzer.canonical(analysis) + b"\n")
    analyzer.maybe_seal_analysis_error(
        valid,
        packet_for(valid),
        SHA,
        RuntimeError("duplicate analyze"),
    )
    assert not (valid / "analysis.error.json").exists()


def test_downstream_authority_only_advances_to_preregistration_construction() -> None:
    passed = analyzer.downstream_after_analysis(True)
    assert passed["counter_gate_evaluated"] is True
    assert passed["endpoint_preregistration_construction_authorized"] is True
    assert passed["endpoint_authorized"] is False
    assert passed["model_generation_authorized"] is False
    assert passed["network_authorized"] is False
    assert passed["submission_authorized"] is False


def test_full_synthetic_runner_tree_seals_all_analyzer_phases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the real capture schemas from an open runner-style tree.

    System-observation leaves are deliberately stubbed: this is a CPU test.
    Everything above those leaves (all 16 manifests, parser-compatible profiler
    bytes, hashes, inventories, analysis, terminal seal, and final rehash) is
    real analyzer/runner code.
    """
    runs = tmp_path / "runs"
    root = runs / "shared-gate-up-m8-counters-20260724T120000Z"
    runs.mkdir()
    root.mkdir()
    monkeypatch.setattr(analyzer.contract, "RUNS", runs)

    def environment(base: str, _rank: int) -> dict[str, str]:
        return {
            name: str(path)
            for name, path in analyzer.runner.private_runtime_paths(Path(base)).items()
        }

    monkeypatch.setattr(analyzer.component, "environment", environment)
    monkeypatch.setattr(analyzer.runner.component_contract, "environment", environment)
    # These five leaves are host observations, independently unit-tested above;
    # stubbing them keeps this closure test entirely CPU/local and deterministic.
    monkeypatch.setattr(analyzer, "validate_source", lambda value, *_: value)
    monkeypatch.setattr(analyzer, "validate_device", lambda value, *_: value)
    monkeypatch.setattr(analyzer, "validate_idle", lambda value, *_: value)
    monkeypatch.setattr(analyzer, "validate_mount", lambda value, *_: value)
    monkeypatch.setattr(analyzer, "validate_sudo_metadata", lambda value, *_: value)

    packet_sha = "b" * 64
    protocol = {"synthetic": True}
    protocol_sha = analyzer.canonical_sha(protocol)
    tooling = {
        "fixture": {"sha256": "c" * 64},
        "component_contract": {"path": "x", "sha256": "d" * 64},
        "component_runtime": {"path": "y", "sha256": "e" * 64},
        "stage0_runtime": {"path": "z", "sha256": "f" * 64},
        "runner": {"sha256": "0" * 64},
    }
    packet = {
        "packet_path": "/synthetic/authorization.json",
        "protocol": protocol,
        "acceptance": {"synthetic": True},
        "actions": {"synthetic": True},
        "component_evidence": {"synthetic": True},
        "tooling": tooling,
        "identity": {"synthetic": True},
        "campaign": {
            "root": str(root),
            "intent": str(root / "campaign.intent.json"),
            "open": str(root / "campaign.open.json"),
            "complete": str(root / "campaign.complete.json"),
            "analysis": str(root / analyzer.ANALYSIS_NAME),
            "terminal": str(root / analyzer.TERMINAL_NAME),
            "final_manifest": str(root / analyzer.FINAL_NAME),
        },
    }
    downstream = {name: False for name in analyzer.runner.DOWNSTREAM_FALSE}

    def write(path: Path, value: dict) -> None:
        path.write_bytes(analyzer.canonical(value) + b"\n")

    def entry(path: Path) -> dict:
        return {
            "path": str(path),
            "sha256": analyzer.sha(path),
            "bytes": path.stat().st_size,
        }

    def write_profiler(timing: Path, metrics: Path, kernel: str) -> None:
        timing_rows = [
            ("zeCommandListAppendMemoryCopy(D2M)[1572864]", 2, 20),
            (kernel, 26, 260),
            ("zeCommandListAppendMemoryCopy(M2D)[1572864]", 2, 20),
            ("zeCommandListAppendMemoryCopy(D2M)[49152]", 1, 10),
            ("zeCommandListAppendMemoryCopy(D2M)[4096]", 26, 260),
            ("zeCommandListAppendMemoryCopy(M2D)[49152]", 1, 10),
        ]
        with timing.open("w", newline="") as handle:
            handle.write(
                "=== Device Timing Summary ===\n\nTotal Device Time for L0 backend (ns): 580\n\n"
            )
            writer = csv.DictWriter(
                handle, fieldnames=analyzer.counter_parser.TIMING_FIELDS
            )
            writer.writeheader()
            for name, calls, elapsed in timing_rows:
                writer.writerow(
                    {
                        "Kernel": name,
                        "Calls": calls,
                        "Time (ns)": elapsed,
                        "Time (%)": f"{elapsed * 100 / 580:.6f}",
                        "Average (ns)": 10,
                        "Min (ns)": 9,
                        "Max (ns)": 11,
                    }
                )
            handle.write("\n=== Kernel Properties ===\n\n")
            writer = csv.DictWriter(
                handle, fieldnames=analyzer.counter_parser.PROPERTY_FIELDS
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Kernel": kernel,
                    "Compiled": "AOT",
                    "SIMD": "16",
                    "Number of Arguments": "15",
                    "SLM Per Work Group": "0",
                    "Private Memory Per Thread": "0",
                    "Spill Memory Per Thread": "0",
                    "Register File Size Per Thread": "256",
                }
            )
        with metrics.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=analyzer.counter_parser.METRIC_FIELDS
            )
            writer.writeheader()
            for index in range(26):
                row = {field: "1" for field in analyzer.counter_parser.METRIC_FIELDS}
                row.update(
                    {
                        field: "0"
                        for field in analyzer.counter_parser.ZERO_VALIDITY_FIELDS
                        + analyzer.counter_parser.ZERO_TRAFFIC_FIELDS
                    }
                )
                row.update(
                    {
                        "Kernel": kernel,
                        "GlobalInstanceId": str((index // 2) * 3 + index % 2),
                        "SubDeviceId": "0",
                        "ReportsCount": "1",
                        "XVE_ACTIVE[%]": "50",
                        "XVE_STALL[%]": "25",
                        "XVE_THREADS_OCCUPANCY_ALL[%]": "75",
                    }
                )
                writer.writerow(row)

    write(
        root / "campaign.intent.json",
        {
            "format": "laguna-shared-gate-up-m8-counter-campaign-intent-v1",
            "status": "started",
            "created_utc": "2026-07-24T12:00:00Z",
            "campaign_root": str(root),
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "protocol_sha256": protocol_sha,
            "counter_execution_performed": False,
            **downstream,
        },
    )
    # The open record is schema-complete; system-observation leaves are harmless
    # placeholders because their validators are intentionally stubbed above.
    write(
        root / "campaign.open.json",
        {
            "format": "laguna-shared-gate-up-m8-counter-campaign-open-v1",
            "status": "open",
            "created_utc": "2026-07-24T12:00:00Z",
            "campaign_root": str(root),
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "packet_actions": packet["actions"],
            "protocol": protocol,
            "protocol_sha256": protocol_sha,
            "acceptance": packet["acceptance"],
            "component_evidence": packet["component_evidence"],
            "tooling": tooling,
            "identity": packet["identity"],
            "campaign_specification": packet["campaign"],
            "campaign_intent": {
                "path": str(root / "campaign.intent.json"),
                "sha256": analyzer.sha(root / "campaign.intent.json"),
            },
            "source": {},
            "mount": {},
            "pre_root_preflight": {
                "devices": [{}, {}, {}, {}],
                "idle": {},
                "sudo_password_file": {},
            },
            "planned_cards": [0, 1, 2, 3],
            "planned_arms_per_card": list(analyzer.ARMS),
            "counter_execution_performed": False,
            **downstream,
        },
    )
    arms: list[dict] = []
    cards: list[dict] = []
    for rank in analyzer.RANKS:
        card_arms: list[dict] = []
        for arm in analyzer.ARMS:
            base = root / f"card{rank}" / arm
            base.mkdir(parents=True)
            env = environment(str(base), rank)
            for value in env.values():
                Path(value).mkdir(parents=True, exist_ok=True)
            treatment = "control" if arm.startswith("A") else "candidate"
            kernel = CONTROL_KERNEL if treatment == "control" else CANDIDATE_KERNEL
            suffix = "1234"
            command = analyzer.runner.unitrace_argv(
                rank, arm, base, tooling["fixture"]["sha256"], packet_sha, protocol_sha
            )
            write(
                base / "preflight.json",
                {
                    "format": "laguna-shared-gate-up-m8-counter-arm-preflight-v1",
                    "status": "passed",
                    "rank": rank,
                    "arm": arm,
                    "treatment": treatment,
                    "authorization_path": packet["packet_path"],
                    "authorization_sha256": packet_sha,
                    "protocol_sha256": protocol_sha,
                    "source": {},
                    "physical_device": {"expected": analyzer.contract.CARDS[rank]},
                    "idle": {},
                    "mount": {},
                    "sudo_password_file": {},
                    "environment": env,
                },
            )
            (base / "stdout.log").write_bytes(b"")
            (base / "stderr.log").write_bytes(b"")
            inputs = {
                name: hashlib.sha256(name.encode()).hexdigest()
                for name in ("rows", "gate_weight", "up_weight")
            }
            inputs["combined"] = hashlib.sha256(
                json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            boundary = {
                name: hashlib.sha256(f"all:{name}".encode()).hexdigest()
                for name in ("gate", "up")
            }
            fixture = {
                "format": "laguna-shared-gate-up-mm-cold-counter-fixture-v2",
                "status": "fixture-complete",
                "created_utc": "2026-07-24T12:00:00Z",
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "fixture_source_sha256": tooling["fixture"]["sha256"],
                "rank": rank,
                "arm": treatment,
                "epoch": 30_000,
                "geometry": {
                    "rows": 8,
                    "k": 3072,
                    "n": 256,
                    "dtype": "torch.bfloat16",
                    "rows_contiguous": True,
                    "gate_weight_contiguous": True,
                    "up_weight_contiguous": True,
                },
                "pair_order": ["gate_proj", "up_proj"],
                "pairs": 13,
                "selected_pair_invocations": 13,
                "selected_gemm_calls": 26,
                "control_primitives_per_pair": ["torch.bmm", "torch.bmm"],
                "candidate_primitives_per_pair": ["torch.mm", "torch.mm"],
                "completion_boundary_before_each_pair": True,
                "completion_boundary_after_each_pair": True,
                "eviction_bytes_before_each_pair": 128 * 1024 * 1024,
                "input_sha256": inputs,
                "input_fixture_sha256": inputs["combined"],
                "boundary_sha256": boundary,
                "all_pair_output_sha256": [
                    {"pair": str(index), **boundary} for index in range(13)
                ],
                "counter_execution_performed": True,
                "counter_gate_evaluated": False,
                "endpoint_preregistration_construction_authorized": False,
                "endpoint_authorized": False,
                "model_generation_performed": False,
                "payload_created": False,
                "submission_performed": False,
                "identity": {
                    "captured_utc": "2026-07-24T12:00:00Z",
                    "pid": int(suffix),
                    "argv": command[command.index(str(analyzer.runner.FIXTURE)) :],
                    "fixture": {
                        "path": str(analyzer.runner.FIXTURE),
                        "sha256": tooling["fixture"]["sha256"],
                    },
                    "component_contract": {
                        "path": str(
                            analyzer.contract.MAIN
                            / tooling["component_contract"]["path"]
                        ),
                        "sha256": tooling["component_contract"]["sha256"],
                    },
                    "component_runtime": {
                        "path": str(
                            analyzer.contract.MAIN
                            / tooling["component_runtime"]["path"]
                        ),
                        "sha256": tooling["component_runtime"]["sha256"],
                    },
                    "stage0_runtime": {
                        "path": str(
                            analyzer.contract.MAIN / tooling["stage0_runtime"]["path"]
                        ),
                        "sha256": tooling["stage0_runtime"]["sha256"],
                    },
                    "model_config": {
                        "path": str(analyzer.contract.MODEL_CONFIG),
                        "sha256": analyzer.contract.EXPECTED["model_config_sha256"],
                    },
                    "environment": env,
                    "boot_id": analyzer.contract.EXPECTED["boot_id"],
                    "kernel_taint": "0",
                    "visible_torch_xpu_count": 1,
                    "visible_torch_xpu_name": analyzer.contract.CARDS[rank][
                        "device_name"
                    ],
                    "expected_physical_device": analyzer.component.CARDS[rank],
                    "mount": {
                        "target": "/mnt/fast-ai",
                        "mount_point": "/",
                        "source": analyzer.contract.EXPECTED["nvme_source"],
                        "filesystem": analyzer.contract.EXPECTED["nvme_fstype"],
                    },
                    "subprocesses_started": 0,
                },
            }
            write(base / "fixture.json", fixture)
            write_profiler(
                base / f"unitrace.{suffix}", base / f"unitrace.metrics.{suffix}", kernel
            )
            write(
                base / "post-arm-idle.json",
                {
                    "text": "",
                    "sha256": hashlib.sha256(b"").hexdigest(),
                    "passed": True,
                    "rows": 4,
                    "only_xpu_smi_self_rows": True,
                },
            )
            evidence = [
                base / name
                for name in (
                    "preflight.json",
                    "stdout.log",
                    "stderr.log",
                    "fixture.json",
                    f"unitrace.{suffix}",
                    f"unitrace.metrics.{suffix}",
                    "post-arm-idle.json",
                )
            ]
            write(
                base / "manifest.json",
                {
                    "format": "laguna-shared-gate-up-m8-counter-arm-manifest-v1",
                    "status": "complete",
                    "completed_utc": "2026-07-24T12:00:00Z",
                    "rank": rank,
                    "arm": arm,
                    "treatment": treatment,
                    "authorization_path": packet["packet_path"],
                    "authorization_sha256": packet_sha,
                    "protocol_sha256": protocol_sha,
                    "command": command,
                    "environment": env,
                    "cwd": str(base),
                    "returncode": 0,
                    "unitrace_output_pid_suffix": suffix,
                    "runtime_subtree": {
                        "path": str(base / "runtime"),
                        "private": True,
                        "excluded_from_evidence_hashes": True,
                    },
                    "files": {path.name: entry(path) for path in evidence},
                    "fixture": fixture,
                    "counter_execution_performed": True,
                    **downstream,
                },
            )
            record = {
                "rank": rank,
                "arm": arm,
                "treatment": treatment,
                "path": str(base / "manifest.json"),
                "sha256": analyzer.sha(base / "manifest.json"),
            }
            arms.append(record)
            card_arms.append(record)
        card = root / f"card{rank}"
        write(
            card / "post-card-idle.json",
            {
                "text": "",
                "sha256": hashlib.sha256(b"").hexdigest(),
                "passed": True,
                "rows": 4,
                "only_xpu_smi_self_rows": True,
            },
        )
        write(
            card / "card.manifest.json",
            {
                "format": "laguna-shared-gate-up-m8-counter-card-manifest-v1",
                "status": "complete",
                "completed_utc": "2026-07-24T12:00:00Z",
                "rank": rank,
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "arms": card_arms,
                "post_card_idle": {
                    "path": str(card / "post-card-idle.json"),
                    "sha256": analyzer.sha(card / "post-card-idle.json"),
                },
                "counter_execution_performed": True,
                **downstream,
            },
        )
        cards.append(
            {
                "rank": rank,
                "path": str(card / "card.manifest.json"),
                "sha256": analyzer.sha(card / "card.manifest.json"),
            }
        )
    write(
        root / "final-idle.json",
        {
            "text": "",
            "sha256": hashlib.sha256(b"").hexdigest(),
            "passed": True,
            "rows": 4,
            "only_xpu_smi_self_rows": True,
        },
    )
    write(
        root / "campaign.complete.json",
        {
            "format": "laguna-shared-gate-up-m8-counter-campaign-complete-v1",
            "status": "complete",
            "completed_utc": "2026-07-24T12:00:00Z",
            "campaign_root": str(root),
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "protocol_sha256": protocol_sha,
            "campaign_open": {
                "path": str(root / "campaign.open.json"),
                "sha256": analyzer.sha(root / "campaign.open.json"),
            },
            "cards": cards,
            "arms": arms,
            "final_idle": {
                "path": str(root / "final-idle.json"),
                "sha256": analyzer.sha(root / "final-idle.json"),
            },
            "counter_execution_performed": True,
            **downstream,
        },
    )

    analyzer.validate_capture(root, packet, packet_sha, phase="analyze")
    analysis = analyzer.perform_analysis(root, packet, packet_sha)
    assert analysis["status"] == "counter-failed-stop-before-endpoint"
    analyzer.validate_capture(root, packet, packet_sha, phase="finalize")
    analyzer.perform_finalize(root, packet, packet_sha)
    (root / analyzer.FINAL_NAME).unlink()
    analyzer.validate_capture(root, packet, packet_sha, phase="terminal-only")
    analyzer.durable_exclusive_json(
        root / analyzer.FINAL_NAME,
        analyzer.final_manifest_payload(root, packet_sha, analysis),
    )
    analyzer.validate_capture(root, packet, packet_sha, phase="final")
    analyzer.verify_final(root, packet, packet_sha)
