"""CPU-only parser, threshold, and tamper tests for shared-down counters."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

import analyze_laguna_shared_down_mm_counters as analyzer
import run_laguna_shared_down_mm_counters as runner


KERNEL = "gemm_kernel[SIMD16 {32; 1; 1} {32; 2; 8}]"
BASE_FIELDS = (
    "Kernel",
    "GlobalInstanceId",
    "SubDeviceId",
    "ReportsCount",
)
FIELDS = tuple(
    dict.fromkeys(
        (
            *BASE_FIELDS,
            *analyzer.MEAN_FIELDS,
            *analyzer.ZERO_VALIDITY_FIELDS,
            *analyzer.ZERO_TRAFFIC_FIELDS,
        )
    )
)


def metric_row(index: int) -> dict[str, str]:
    row = {field: "10" for field in FIELDS}
    row.update(
        {
            "Kernel": KERNEL,
            "GlobalInstanceId": str(100 + index),
            "SubDeviceId": "0",
            "ReportsCount": "1",
            "XVE_ACTIVE[%]": "80",
            "XVE_STALL[%]": "20",
            "XVE_THREADS_OCCUPANCY_ALL[%]": "75",
        }
    )
    row.update({field: "0" for field in analyzer.ZERO_VALIDITY_FIELDS})
    row.update({field: "0" for field in analyzer.ZERO_TRAFFIC_FIELDS})
    return row


def write_metrics(
    path: Path,
    rows: list[dict[str, str]] | None = None,
) -> Path:
    rows = rows or [metric_row(index) for index in range(13)]
    with path.open("w", newline="") as handle:
        handle.write("unitrace metric-query evidence\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_timing(
    path: Path,
    *,
    kernel: str = KERNEL,
    calls: str = "13",
    time_ns: str = "130",
    time_percent: str = "100",
    average_ns: str = "10",
    minimum_ns: str = "9",
    maximum_ns: str = "11",
    compiled: str = "AOT",
    simd: str = "16",
    argument_count: str = "3",
    spill: str = "0",
    slm: str = "0",
    private_memory: str = "0",
    register_file: str = "128",
) -> Path:
    path.write_text(
        "\n".join(
            (
                "=== Device Timing Summary ===",
                "  Kernel, Calls, Time (ns), Time (%), Average (ns), Min (ns), Max (ns)",
                f"  {kernel}, {calls}, {time_ns}, {time_percent}, {average_ns}, {minimum_ns}, {maximum_ns}",
                "=== Kernel Properties ===",
                "  Kernel, Compiled, SIMD, Number of Arguments, SLM Per Work Group, Private Memory Per Thread, Spill Memory Per Thread, Register File Size Per Thread",
                f"  {kernel}, {compiled}, {simd}, {argument_count}, {slm}, {private_memory}, {spill}, {register_file}",
                "",
            )
        )
    )
    return path


def test_metrics_accept_exact_contract_and_discard_two(tmp_path: Path) -> None:
    parsed = analyzer.parse_metrics(write_metrics(tmp_path / "unitrace.metrics.7"))
    assert parsed["raw_selected_queries"] == 13
    assert parsed["discarded_query_indexes"] == [0, 1]
    assert parsed["analyzed_queries"] == 11
    assert parsed["kernel_name"] == KERNEL


def test_metrics_accept_zero_stall(tmp_path: Path) -> None:
    rows = [metric_row(index) for index in range(13)]
    for row in rows:
        row["XVE_STALL[%]"] = "0"
    analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


@pytest.mark.parametrize("field", analyzer.ZERO_VALIDITY_FIELDS)
def test_metrics_reject_every_validity_proxy(tmp_path: Path, field: str) -> None:
    rows = [metric_row(index) for index in range(13)]
    rows[4][field] = "1"
    with pytest.raises(RuntimeError, match=field.replace("[", r"\[")):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


@pytest.mark.parametrize("field", analyzer.ZERO_TRAFFIC_FIELDS)
def test_metrics_reject_every_zero_traffic_proxy(
    tmp_path: Path,
    field: str,
) -> None:
    rows = [metric_row(index) for index in range(13)]
    rows[5][field] = "1"
    with pytest.raises(RuntimeError, match="nonzero"):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


def test_metrics_reject_duplicate_or_unordered_ids(tmp_path: Path) -> None:
    rows = [metric_row(index) for index in range(13)]
    rows[4]["GlobalInstanceId"] = rows[3]["GlobalInstanceId"]
    with pytest.raises(RuntimeError, match="duplicate"):
        analyzer.parse_metrics(write_metrics(tmp_path / "duplicate", rows))
    rows = [metric_row(index) for index in range(13)]
    rows[4]["GlobalInstanceId"] = "1"
    with pytest.raises(RuntimeError, match="not ordered"):
        analyzer.parse_metrics(write_metrics(tmp_path / "unordered", rows))


@pytest.mark.parametrize("count", (12, 14))
def test_metrics_reject_wrong_row_count(tmp_path: Path, count: int) -> None:
    rows = [metric_row(index) for index in range(count)]
    with pytest.raises(RuntimeError, match="exactly 13"):
        analyzer.parse_metrics(write_metrics(tmp_path / f"metrics-{count}", rows))


@pytest.mark.parametrize(
    "kernel",
    (
        "gemm_kernel",
        "gemm_kernel[SIMD8 {32; 1; 1} {32; 2; 8}]",
        "other_gemm_kernel[SIMD16 {32; 1; 1} {32; 2; 8}]",
    ),
)
def test_metrics_reject_nonfrozen_kernel_forms(
    tmp_path: Path,
    kernel: str,
) -> None:
    rows = [metric_row(index) for index in range(13)]
    for row in rows:
        row["Kernel"] = kernel
    with pytest.raises(RuntimeError, match="verbose SIMD16"):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


def test_metrics_reject_mixed_kernel_identity(tmp_path: Path) -> None:
    rows = [metric_row(index) for index in range(13)]
    rows[-1]["Kernel"] = "gemm_kernel[SIMD16 {64; 1; 1} {16; 4; 8}]"
    with pytest.raises(RuntimeError, match="one exact"):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("GpuTime[ns]", "0"),
        ("GPU_MEMORY_BYTE_READ[bytes]", "nan"),
        ("XVE_ACTIVE[%]", "101"),
        ("XVE_STALL[%]", "-1"),
        ("ReportsCount", "2"),
        ("ReportsCount", "1.0"),
    ),
)
def test_metrics_reject_invalid_scalars(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    rows = [metric_row(index) for index in range(13)]
    rows[3][field] = value
    with pytest.raises(RuntimeError):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


def test_metrics_reject_wrong_subdevice_id(tmp_path: Path) -> None:
    rows = [metric_row(index) for index in range(13)]
    for row in rows:
        row["SubDeviceId"] = "999"
    with pytest.raises(RuntimeError, match="SubDeviceId"):
        analyzer.parse_metrics(write_metrics(tmp_path / "metrics", rows))


def test_timing_properties_accept_padded_headers(tmp_path: Path) -> None:
    parsed = analyzer.parse_timing_properties(
        write_timing(tmp_path / "unitrace.7"),
        expected_kernel_name=KERNEL,
    )
    assert parsed["calls"] == 13
    assert parsed["spill_memory_per_thread"] == 0
    assert parsed["slm_per_work_group"] == 0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"calls": "12"}, "Calls"),
        ({"spill": "1"}, "spill"),
        ({"slm": "1"}, "SLM"),
        (
            {"kernel": "gemm_kernel[SIMD16 {64; 1; 1} {16; 4; 8}]"},
            "selected exact kernel",
        ),
    ),
)
def test_timing_properties_reject_tamper(
    tmp_path: Path,
    kwargs: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(RuntimeError, match=match):
        analyzer.parse_timing_properties(
            write_timing(tmp_path / "unitrace", **kwargs),
            expected_kernel_name=KERNEL,
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"time_ns": "nan"}, "emitter-form decimal integer"),
        ({"time_ns": "130.0"}, "emitter-form decimal integer"),
        ({"time_percent": "-999"}, "timing scalar"),
        ({"average_ns": "-1"}, "emitter-form decimal integer"),
        ({"minimum_ns": "12"}, "timing scalar"),
        ({"maximum_ns": "8"}, "timing scalar"),
        ({"time_ns": "143", "average_ns": "10"}, "inconsistent"),
        (
            {
                "time_ns": "139",
                "average_ns": "10",
                "minimum_ns": "10",
                "maximum_ns": "10",
            },
            "inconsistent",
        ),
        (
            {
                "time_ns": "1000000",
                "time_percent": "1",
                "average_ns": "10",
            },
            "timing scalar",
        ),
        ({"compiled": "INVALID"}, "compilation mode"),
        ({"simd": "8"}, "SIMD"),
        ({"argument_count": "0"}, "no arguments"),
        ({"private_memory": "-1"}, "emitter-form decimal integer"),
        ({"register_file": "0"}, "private/register"),
    ),
)
def test_timing_properties_reject_schema_scalar_tamper(
    tmp_path: Path,
    kwargs: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(RuntimeError, match=match):
        analyzer.parse_timing_properties(
            write_timing(tmp_path / "unitrace", **kwargs),
            expected_kernel_name=KERNEL,
        )


def base_means() -> dict[str, float]:
    return {field: 100.0 for field in analyzer.MEAN_FIELDS}


def synthetic_profile(rank: int, arm: str) -> dict[str, object]:
    treatment = "control" if arm.startswith("A") else "candidate"
    means = base_means()
    if treatment == "candidate":
        means["GpuTime[ns]"] = 99.0
    output_hash = "b" * 64
    return {
        "rank": rank,
        "arm": arm,
        "treatment": treatment,
        "preflight": {
            "physical_uuid": runner.EXPECTED_PHYSICAL_DEVICES[rank]["uuid"],
            "physical_bdf": runner.EXPECTED_PHYSICAL_DEVICES[rank]["pci_bdf_address"],
            "main_commit": "1" * 40,
            "vllm_commit": runner.EXPECTED_VLLM_COMMIT,
            "kernel_commit": runner.EXPECTED_KERNEL_COMMIT,
            "boot_id": runner.EXPECTED_BOOT_ID,
        },
        "fixture": {
            "fixture_sha256": "a" * 64,
            "input_sha256": {
                "rows": "c" * 64,
                "weight": "d" * 64,
                "combined": "a" * 64,
            },
            "output_sha256": output_hash,
            "all_output_sha256": [output_hash] * 13,
            "torch": runner.EXPECTED_TORCH_VERSION,
            "torch_path": runner.EXPECTED_TORCH_FILES["__init__"]["path"],
        },
        "metrics": {
            "kernel_name": (
                KERNEL
                if treatment == "control"
                else "gemm_kernel[SIMD16 {64; 1; 1} {16; 4; 8}]"
            ),
            "mean": means,
        },
    }


def synthetic_profiles() -> list[dict[str, object]]:
    return [
        synthetic_profile(rank, arm) for rank in runner.RANKS for arm in runner.ARMS
    ]


def test_profile_analysis_accepts_exact_four_card_abba() -> None:
    result = analyzer.analyze_profiles(synthetic_profiles())
    assert result["passed"] is True
    assert result["all_control_candidate_outputs_raw_exact"] is True
    assert all(card["passed"] for card in result["cards"].values())
    assert result["global_four_card_candidate_vs_control"]["passed"] is True


def test_profile_analysis_rejects_coverage_and_raw_output_tamper() -> None:
    profiles = synthetic_profiles()
    with pytest.raises(RuntimeError, match="coverage"):
        analyzer.analyze_profiles(profiles[:-1])
    profiles = synthetic_profiles()
    profiles[5]["fixture"]["output_sha256"] = "e" * 64
    with pytest.raises(RuntimeError, match="raw output"):
        analyzer.analyze_profiles(profiles)


def test_profile_analysis_rejects_source_physical_and_kernel_tamper() -> None:
    profiles = synthetic_profiles()
    profiles[4]["preflight"]["physical_uuid"] = profiles[0]["preflight"][
        "physical_uuid"
    ]
    with pytest.raises(RuntimeError, match="physical/source/runtime"):
        analyzer.analyze_profiles(profiles)
    profiles = synthetic_profiles()
    profiles[1]["metrics"]["kernel_name"] = "gemm_kernel[SIMD16 {128; 1; 1} {8; 8; 8}]"
    with pytest.raises(RuntimeError, match="kernel identity"):
        analyzer.analyze_profiles(profiles)


def test_profile_analysis_rejects_pair_and_aggregate_gates() -> None:
    profiles = synthetic_profiles()
    by = {(profile["rank"], profile["arm"]): profile for profile in profiles}
    by[0, "B1"]["metrics"]["mean"]["GpuTime[ns]"] = 100.0
    result = analyzer.analyze_profiles(profiles)
    assert result["passed"] is False
    assert result["cards"]["0"]["B1_vs_A1"]["passed"] is False

    profiles = synthetic_profiles()
    by = {(profile["rank"], profile["arm"]): profile for profile in profiles}
    for arm in ("B1", "B2"):
        by[0, arm]["metrics"]["mean"]["GPU_MEMORY_BYTE_READ[bytes]"] = 103.0
    result = analyzer.analyze_profiles(profiles)
    assert result["passed"] is False
    assert result["cards"]["0"]["B1_vs_A1"]["passed"] is True
    assert result["cards"]["0"]["candidate_vs_control_aggregate"]["passed"] is False

    profiles = synthetic_profiles()
    for profile in profiles:
        if profile["treatment"] == "candidate":
            profile["metrics"]["mean"]["GpuTime[ns]"] = 101.0
    result = analyzer.analyze_profiles(profiles)
    assert result["passed"] is False
    assert result["global_four_card_candidate_vs_control"]["passed"] is False
    assert result["global_four_card_candidate_vs_control"]["checks"] == {
        "candidate_gpu_time_lower": False
    }


def test_comparison_accepts_exact_threshold_contract() -> None:
    control = base_means()
    candidate = copy.deepcopy(control)
    candidate["GpuTime[ns]"] = 99.0
    candidate["GPU_MEMORY_BYTE_READ[bytes]"] = 102.0
    candidate["LOAD_STORE_CACHE_BYTE_READ[bytes]"] = 102.0
    candidate["XVE_STALL[%]"] = 100.5
    candidate["XVE_ACTIVE[%]"] = 99.5
    candidate["XVE_THREADS_OCCUPANCY_ALL[%]"] = 99.5
    assert (
        analyzer.compare_means(
            candidate,
            control,
            full_metric_guardrails=True,
        )["passed"]
        is True
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("GpuTime[ns]", 100.0),
        ("GPU_MEMORY_BYTE_READ[bytes]", 102.0001),
        ("LOAD_STORE_CACHE_BYTE_READ[bytes]", 102.0001),
        ("XVE_STALL[%]", 100.5001),
        ("XVE_ACTIVE[%]", 99.4999),
        ("XVE_THREADS_OCCUPANCY_ALL[%]", 99.4999),
    ),
)
def test_comparison_rejects_each_threshold(
    field: str,
    value: float,
) -> None:
    control = base_means()
    candidate = copy.deepcopy(control)
    candidate["GpuTime[ns]"] = 99.0
    candidate[field] = value
    assert (
        analyzer.compare_means(
            candidate,
            control,
            full_metric_guardrails=True,
        )["passed"]
        is False
    )


def test_pair_scope_checks_gpu_time_only() -> None:
    control = base_means()
    candidate = copy.deepcopy(control)
    candidate["GpuTime[ns]"] = 99.0
    candidate["GPU_MEMORY_BYTE_READ[bytes]"] = 500.0
    result = analyzer.compare_means(
        candidate,
        control,
        full_metric_guardrails=False,
    )
    assert result["passed"] is True
    assert result["checks"] == {"candidate_gpu_time_lower": True}


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_packet() -> dict[str, object]:
    return {
        "authorization": {
            "component_passed": True,
            "counter_tooling_construction_authorized": True,
            "counter_execution_authorized": True,
            "counter_gate_evaluated": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_authorized": False,
            "model_generation_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_authorized": False,
            "localmaxxing_submission_made": False,
        },
        "protocol": runner.expected_protocol(),
        "acceptance": runner.expected_acceptance(),
        "tools": {
            "fixture": {
                "path": str(runner.FIXTURE),
                "sha256": "1" * 64,
            },
            "gate": {
                "path": str(runner.GATE),
                "sha256": "2" * 64,
            },
        },
        "component_evidence": runner.expected_component_evidence(),
        "identities": runner.expected_identities(),
    }


def synthetic_source(packet: dict[str, object]) -> dict[str, object]:
    return {
        "repositories": {
            "main": {"clean": True, "commit": "1" * 40},
            "vllm": {"clean": True, "commit": runner.EXPECTED_VLLM_COMMIT},
            "kernels": {"clean": True, "commit": runner.EXPECTED_KERNEL_COMMIT},
            "unitrace_source": {
                "clean": True,
                "commit": runner.EXPECTED_UNITRACE_COMMIT,
            },
        },
        "tools": packet["tools"],
        "python": packet["identities"]["python"],
        "torch": packet["identities"]["torch"],
        "host_tools": packet["identities"]["host_tools"],
        "boot_id": runner.EXPECTED_BOOT_ID,
        "kernel_taint": "0",
    }


def create_runtime_tree(base: Path) -> dict[str, object]:
    for path in set(runner.arm_runtime_paths(base).values()):
        path.mkdir(parents=True, exist_ok=True)
    runtime = base / "runtime"
    return {
        "path": str(runtime),
        "evidence_file_hashing_excluded": True,
        "reason": "fresh per-arm compiler/cache/temp contents are non-counter evidence",
        "required_directories": {
            name: str(path) for name, path in runner.arm_runtime_paths(base).items()
        },
    }


def synthetic_preflight(
    packet: dict[str, object],
    *,
    rank: int = 0,
    arm: str = "A1",
    packet_sha256: str = "9" * 64,
) -> dict[str, object]:
    expected = runner.EXPECTED_PHYSICAL_DEVICES[rank]
    idle_text = "\n".join(
        (
            "PID Command DeviceID SHR MEM",
            "101 xpu-smi 0 0 0",
            "102 xpu-smi 1 0 0",
            "103 xpu-smi 2 0 0",
            "104 xpu-smi 3 0 0",
            "",
        )
    )
    return {
        "format": "laguna-shared-down-mm-counter-arm-preflight-v1",
        "status": "passed",
        "captured_utc": "2026-07-23T17:00:00+00:00",
        "rank": rank,
        "arm": arm,
        "treatment": "control" if arm.startswith("A") else "candidate",
        "authorization_path": str(runner.AUTHORIZATION_PATH),
        "authorization_sha256": packet_sha256,
        "protocol_sha256": runner.canonical_sha256(packet["protocol"]),
        "source": synthetic_source(packet),
        "physical_device": {
            "rank": rank,
            "expected": expected,
            "filtered": {
                "device_list": [
                    {
                        **expected,
                        "device_id": 0,
                        "device_name": runner.EXPECTED_DEVICE_NAME,
                    }
                ]
            },
            "unfiltered": {
                "device_list": [
                    {
                        **runner.EXPECTED_PHYSICAL_DEVICES[physical_rank],
                        "device_name": runner.EXPECTED_DEVICE_NAME,
                    }
                    for physical_rank in runner.RANKS
                ]
            },
            "uuid_bdf_binding_exact": True,
            "filtered_sha256": "3" * 64,
            "unfiltered_sha256": "4" * 64,
        },
        "idle": {
            "passed": True,
            "only_xpu_smi_self_rows": True,
            "rows": 4,
            "text": idle_text,
            "sha256": hashlib.sha256(idle_text.encode()).hexdigest(),
        },
        "mount": {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": runner.NVME_SOURCE,
            "filesystem": runner.NVME_FSTYPE,
        },
        "sudo_password_file": {
            "mode": "0600",
            "content_not_recorded": True,
        },
    }


def synthetic_fixture(
    base: Path,
    packet: dict[str, object],
    *,
    rank: int = 0,
    arm: str = "A1",
    pid: int = 4242,
) -> tuple[dict[str, object], list[str]]:
    treatment = "control" if arm.startswith("A") else "candidate"
    command = runner.build_unitrace_command(
        rank=rank,
        arm=arm,
        arm_dir=base,
        fixture_sha256=packet["tools"]["fixture"]["sha256"],
    )
    environment = {
        assignment.split("=", maxsplit=1)[0]: assignment.split("=", maxsplit=1)[1]
        for assignment in runner.child_environment_assignments(rank, base)
    }
    input_sha256 = {
        "rows": "5" * 64,
        "weight": "6" * 64,
        "combined": "7" * 64,
    }
    output_sha256 = "8" * 64
    fixture = {
        "format": "laguna-shared-down-mm-cold-counter-fixture-v1",
        "status": "fixture-complete",
        "created_utc": "2026-07-23T17:00:00+00:00",
        "identity": {
            "fixture": packet["tools"]["fixture"],
            "gate": packet["tools"]["gate"],
            "model_config": packet["identities"]["model_config"],
            "binaries": packet["identities"]["runtime_binaries"],
            "torch_identity": packet["identities"]["torch"],
            "declared_physical_rank": rank,
            "expected_physical_device": runner.EXPECTED_PHYSICAL_DEVICES[rank],
            "subprocesses_started": 0,
            "environment": environment,
            "runtime": {
                "boot_id": runner.EXPECTED_BOOT_ID,
                "kernel_taint": "0",
                "visible_torch_xpu_count": 1,
                "visible_torch_xpu_name": runner.EXPECTED_DEVICE_NAME,
                "python_executable": str(runner.PYTHON),
                "python_sha256": packet["identities"]["python"]["sha256"],
                "torch": packet["identities"]["torch"]["version"],
                "torch_path": packet["identities"]["torch"]["files"]["__init__"][
                    "path"
                ],
            },
            "uid": 0,
            "pid": pid,
            "argv": analyzer.expected_fixture_argv(command=command),
            "mount": {
                "target": "/mnt/fast-ai",
                "mount_point": "/",
                "source": runner.NVME_SOURCE,
                "filesystem": runner.NVME_FSTYPE,
            },
        },
        "rank": rank,
        "arm": treatment,
        "epoch": 30_000,
        "geometry": {
            "rows": 8,
            "k": 256,
            "n": 3072,
            "dtype": "torch.bfloat16",
            "rows_contiguous": True,
            "weight_contiguous": True,
        },
        "calls": 13,
        "selected_gemm_calls": 13,
        "completion_boundary_before_each_call": True,
        "completion_boundary_after_each_call": True,
        "eviction_bytes_before_each_call": 134_217_728,
        "input_sha256": input_sha256,
        "fixture_sha256": input_sha256["combined"],
        "output_sha256": output_sha256,
        "all_output_sha256": [output_sha256] * 13,
        "counter_execution_performed": True,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "submission_performed": False,
    }
    return fixture, command


def validate_synthetic_preflight(
    preflight: dict[str, object],
    packet: dict[str, object],
) -> None:
    analyzer.validate_preflight(
        preflight,
        path=Path("/tmp/synthetic-preflight.json"),
        rank=0,
        arm="A1",
        treatment="control",
        packet=packet,
        packet_sha256="9" * 64,
        protocol_sha256=runner.canonical_sha256(packet["protocol"]),
    )


def test_preflight_validates_authorization_and_physical_mapping() -> None:
    packet = synthetic_packet()
    validate_synthetic_preflight(synthetic_preflight(packet), packet)
    preflight = synthetic_preflight(packet)
    preflight["authorization_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="preflight identity"):
        validate_synthetic_preflight(preflight, packet)


@pytest.mark.parametrize(
    "field",
    ("uuid", "pci_bdf_address", "drm_device", "device_name"),
)
def test_preflight_rejects_filtered_physical_identity_tamper(field: str) -> None:
    packet = synthetic_packet()
    preflight = synthetic_preflight(packet)
    preflight["physical_device"]["filtered"]["device_list"][0][field] = "tamper"
    with pytest.raises(RuntimeError, match="filtered/unfiltered discovery"):
        validate_synthetic_preflight(preflight, packet)


def test_fixture_validates_pid_and_authorization_boundary(tmp_path: Path) -> None:
    packet = synthetic_packet()
    base = tmp_path / "A1"
    create_runtime_tree(base)
    fixture, command = synthetic_fixture(base, packet)
    report = analyzer.validate_fixture(
        fixture,
        path=base / "fixture.json",
        base=base,
        rank=0,
        treatment="control",
        command=command,
        packet=packet,
    )
    assert report["fixture_pid"] == 4242
    fixture["endpoint_authorized"] = True
    with pytest.raises(RuntimeError, match="fixture authorization boundary"):
        analyzer.validate_fixture(
            fixture,
            path=base / "fixture.json",
            base=base,
            rank=0,
            treatment="control",
            command=command,
            packet=packet,
        )


def test_runtime_subtree_rejects_broken_descendant_symlink(
    tmp_path: Path,
) -> None:
    base = tmp_path / "A1"
    declaration = create_runtime_tree(base)
    analyzer.validate_runtime_subtree(base, declaration)
    (base / "runtime/cache/xdg/broken").symlink_to("/definitely/not/present")
    with pytest.raises(RuntimeError, match="symlink"):
        analyzer.validate_runtime_subtree(base, declaration)


def build_synthetic_arm(
    parent: Path,
    packet: dict[str, object],
) -> tuple[Path, str]:
    base = parent / "A1"
    base.mkdir(parents=True)
    runtime_subtree = create_runtime_tree(base)
    suffix = "4242"
    evidence_names = {
        "preflight.json",
        "stdout.log",
        "stderr.log",
        "fixture.json",
        f"unitrace.{suffix}",
        f"unitrace.metrics.{suffix}",
    }
    for name in evidence_names:
        path = base / name
        if name.endswith(".json"):
            write_json(path, {})
        else:
            path.write_text(f"synthetic {name}\n")
    files = {
        name: {
            "path": str(base / name),
            "sha256": file_sha256(base / name),
            "bytes": (base / name).stat().st_size,
        }
        for name in evidence_names
    }
    command = runner.build_unitrace_command(
        rank=0,
        arm="A1",
        arm_dir=base,
        fixture_sha256=packet["tools"]["fixture"]["sha256"],
    )
    manifest = {
        "format": "laguna-shared-down-mm-counter-arm-manifest-v1",
        "status": "complete",
        "completed_utc": "2026-07-23T17:00:00+00:00",
        "rank": 0,
        "arm": "A1",
        "treatment": "control",
        "authorization_path": str(runner.AUTHORIZATION_PATH),
        "authorization_sha256": "9" * 64,
        "protocol_sha256": runner.canonical_sha256(packet["protocol"]),
        "command": command,
        "cwd": str(base),
        "returncode": 0,
        "unitrace_output_pid_suffix": suffix,
        "runtime_subtree": runtime_subtree,
        "files": files,
        "fixture": {},
        "counter_execution_performed": True,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "localmaxxing_submission_made": False,
    }
    manifest_path = base / "manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path, file_sha256(manifest_path)


def patch_synthetic_arm_validators(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fixture_pid: int = 4242,
) -> None:
    monkeypatch.setattr(
        analyzer,
        "validate_preflight",
        lambda *_args, **_kwargs: synthetic_profile(0, "A1")["preflight"],
    )
    monkeypatch.setattr(
        analyzer,
        "validate_fixture",
        lambda *_args, **_kwargs: {
            **synthetic_profile(0, "A1")["fixture"],
            "fixture_pid": fixture_pid,
        },
    )
    monkeypatch.setattr(
        analyzer,
        "parse_metrics",
        lambda _path: {
            "kernel_name": KERNEL,
            "mean": base_means(),
        },
    )
    monkeypatch.setattr(
        analyzer,
        "parse_timing_properties",
        lambda _path, **_kwargs: {},
    )


def validate_synthetic_arm(
    manifest_path: Path,
    manifest_sha256: str,
    packet: dict[str, object],
) -> None:
    analyzer.validate_arm(
        manifest_path,
        expected_manifest_sha256=manifest_sha256,
        rank=0,
        arm="A1",
        packet=packet,
        packet_sha256="9" * 64,
        protocol_sha256=runner.canonical_sha256(packet["protocol"]),
    )


def test_arm_validator_closes_files_pid_authorization_and_entry_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = synthetic_packet()
    patch_synthetic_arm_validators(monkeypatch)
    manifest_path, manifest_sha256 = build_synthetic_arm(tmp_path / "valid", packet)
    validate_synthetic_arm(manifest_path, manifest_sha256, packet)

    manifest_path, manifest_sha256 = build_synthetic_arm(
        tmp_path / "file-tamper", packet
    )
    (manifest_path.parent / "stdout.log").write_text("tamper\n")
    with pytest.raises(RuntimeError, match="arm evidence identity"):
        validate_synthetic_arm(manifest_path, manifest_sha256, packet)

    manifest_path, _ = build_synthetic_arm(tmp_path / "auth-tamper", packet)
    manifest = json.loads(manifest_path.read_text())
    manifest["endpoint_authorized"] = True
    write_json(manifest_path, manifest)
    with pytest.raises(RuntimeError, match="arm authorization boundary"):
        validate_synthetic_arm(manifest_path, file_sha256(manifest_path), packet)

    manifest_path, manifest_sha256 = build_synthetic_arm(
        tmp_path / "broken-symlink", packet
    )
    (manifest_path.parent / "broken").symlink_to("/definitely/not/present")
    with pytest.raises(RuntimeError, match="unexpected arm files/directories"):
        validate_synthetic_arm(manifest_path, manifest_sha256, packet)

    manifest_path, manifest_sha256 = build_synthetic_arm(
        tmp_path / "pid-tamper", packet
    )
    patch_synthetic_arm_validators(monkeypatch, fixture_pid=9999)
    with pytest.raises(RuntimeError, match="PID suffix"):
        validate_synthetic_arm(manifest_path, manifest_sha256, packet)


def build_synthetic_campaign(
    parent: Path,
) -> tuple[Path, dict[str, object], str]:
    root = parent / "shared-down-m8-counters-20260723T170000Z"
    root.mkdir(parents=True)
    packet = synthetic_packet()
    packet_sha256 = "9" * 64
    protocol_sha256 = runner.canonical_sha256(packet["protocol"])
    arm_entries: list[dict[str, object]] = []
    card_entries: list[dict[str, object]] = []
    for rank in runner.RANKS:
        card_dir = root / f"card{rank}"
        card_dir.mkdir()
        card_arms: list[dict[str, object]] = []
        for arm in runner.ARMS:
            arm_dir = card_dir / arm
            arm_dir.mkdir()
            entry = {
                "rank": rank,
                "arm": arm,
                "treatment": "control" if arm.startswith("A") else "candidate",
                "path": str(arm_dir / "manifest.json"),
                "sha256": f"{rank}{runner.ARMS.index(arm)}".ljust(64, "0"),
            }
            arm_entries.append(entry)
            card_arms.append(entry)
        card_path = card_dir / "card.manifest.json"
        card = {
            "format": "laguna-shared-down-mm-counter-card-manifest-v1",
            "status": "complete",
            "completed_utc": "2026-07-23T17:00:00+00:00",
            "rank": rank,
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "arms": card_arms,
            "counter_execution_performed": True,
            "counter_gate_evaluated": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_made": False,
        }
        write_json(card_path, card)
        card_entries.append(
            {
                "rank": rank,
                "path": str(card_path),
                "sha256": file_sha256(card_path),
            }
        )
    open_path = root / "campaign.open.json"
    opened = {
        "format": "laguna-shared-down-mm-counter-campaign-open-v1",
        "status": "open",
        "created_utc": "2026-07-23T17:00:00+00:00",
        "campaign_root": str(root),
        "authorization_path": str(runner.AUTHORIZATION_PATH),
        "authorization_sha256": packet_sha256,
        "authorization": packet["authorization"],
        "protocol": packet["protocol"],
        "protocol_sha256": protocol_sha256,
        "acceptance": packet["acceptance"],
        "tools": packet["tools"],
        "component_evidence": packet["component_evidence"],
        "source": synthetic_source(packet),
        "mount": {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": runner.NVME_SOURCE,
            "filesystem": runner.NVME_FSTYPE,
        },
        "planned_cards": list(runner.RANKS),
        "planned_arms_per_card": list(runner.ARMS),
        "counter_execution_performed": False,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "localmaxxing_submission_made": False,
    }
    write_json(open_path, opened)
    complete_path = root / "campaign.complete.json"
    complete = {
        "format": "laguna-shared-down-mm-counter-campaign-complete-v1",
        "status": "complete",
        "completed_utc": "2026-07-23T17:01:00+00:00",
        "campaign_root": str(root),
        "authorization_path": str(runner.AUTHORIZATION_PATH),
        "authorization_sha256": packet_sha256,
        "protocol_sha256": protocol_sha256,
        "campaign_open": {
            "path": str(open_path),
            "sha256": file_sha256(open_path),
        },
        "cards": card_entries,
        "arms": arm_entries,
        "counter_execution_performed": True,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "localmaxxing_submission_made": False,
    }
    write_json(complete_path, complete)
    return root, packet, packet_sha256


def validate_synthetic_campaign(
    root: Path,
    packet: dict[str, object],
    packet_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "RUNS_ROOT", root.parent)

    def fake_validate_arm(
        _path: Path,
        *,
        rank: int,
        arm: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        return synthetic_profile(rank, arm)

    monkeypatch.setattr(analyzer, "validate_arm", fake_validate_arm)
    analyzer.validate_campaign(
        root,
        packet=packet,
        packet_sha256=packet_sha256,
    )


def test_campaign_closure_accepts_exact_four_card_abba(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, packet, packet_sha256 = build_synthetic_campaign(tmp_path)
    validate_synthetic_campaign(root, packet, packet_sha256, monkeypatch)


def test_campaign_closure_rejects_open_authorization_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, packet, packet_sha256 = build_synthetic_campaign(tmp_path)
    open_path = root / "campaign.open.json"
    opened = json.loads(open_path.read_text())
    opened["endpoint_authorized"] = True
    write_json(open_path, opened)
    complete_path = root / "campaign.complete.json"
    complete = json.loads(complete_path.read_text())
    complete["campaign_open"]["sha256"] = file_sha256(open_path)
    write_json(complete_path, complete)
    with pytest.raises(RuntimeError, match="campaign-open"):
        validate_synthetic_campaign(root, packet, packet_sha256, monkeypatch)


def test_campaign_closure_rejects_card_authorization_and_extra_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, packet, packet_sha256 = build_synthetic_campaign(tmp_path)
    card_path = root / "card0/card.manifest.json"
    card = json.loads(card_path.read_text())
    card["model_generation_performed"] = True
    write_json(card_path, card)
    complete_path = root / "campaign.complete.json"
    complete = json.loads(complete_path.read_text())
    complete["cards"][0]["sha256"] = file_sha256(card_path)
    write_json(complete_path, complete)
    with pytest.raises(RuntimeError, match="card 0 manifest"):
        validate_synthetic_campaign(root, packet, packet_sha256, monkeypatch)

    root, packet, packet_sha256 = build_synthetic_campaign(tmp_path / "second")
    (root / "card1/unexpected.txt").write_text("tamper\n")
    with pytest.raises(RuntimeError, match="card 1 directory"):
        validate_synthetic_campaign(root, packet, packet_sha256, monkeypatch)


def test_unitrace_template_has_frozen_modern_syntax() -> None:
    template = runner.expected_protocol()["unitrace"]["argv_template"]
    metric_index = template.index("--metric-query")
    assert template[metric_index + 1] == "--group"
    assert template[metric_index + 2] == "ComputeBasic"
    assert template[template.index("--rank") + 1] == "{rank}"
    assert template[template.index("--arm") + 1] == "{treatment}"
    assert "ZE_AFFINITY_MASK={rank}" in template
    assert "--follow-child-process" not in template
    assert template[:7] == [
        "/usr/bin/sudo",
        "-S",
        "-p",
        "",
        "-E",
        "--",
        "/usr/bin/env",
    ]
    assert template[7] == "-i"
    assert "HOME={arm_dir}/runtime/home" in template
    assert "/usr/bin/timeout" in template
    assert "180s" in template
    assert (
        runner.expected_protocol()["unitrace"][
            "runner_timeout_process_group_term_seconds"
        ]
        == 5
    )
    assert (
        runner.expected_protocol()["unitrace"][
            "runner_timeout_process_group_kill_seconds"
        ]
        == 5
    )


def test_component_evidence_matches_pinned_aggregate_and_cards() -> None:
    runner.validate_component_evidence()


def test_outer_timeout_terminates_full_process_group(tmp_path: Path) -> None:
    stdout, stderr, returncode = runner.run_bounded_process_group(
        [
            sys.executable,
            "-c",
            (
                "import subprocess,time;"
                "child=subprocess.Popen(['/usr/bin/sleep','30']);"
                "print(child.pid,flush=True);"
                "time.sleep(30)"
            ),
        ],
        stdin_path=None,
        cwd=tmp_path,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HOME": str(tmp_path),
        },
        timeout_seconds=0.5,
        term_grace_seconds=0.5,
        kill_grace_seconds=2,
    )
    assert returncode == 124
    assert stdout.strip().isdigit()
    assert stderr == b""


def test_tool_sources_contain_no_hash_cycle_placeholders() -> None:
    for path in (runner.RUNNER, runner.ANALYZER, runner.FIXTURE):
        text = path.read_text()
        assert "TODO_ROOT_INSERT" not in text
        assert "EXPECTED_RUNNER_SHA256" not in text
        assert "EXPECTED_ANALYZER_SHA256" not in text
        assert "EXPECTED_AUTHORIZATION_PACKET_SHA256" not in text


def test_fixture_has_no_subprocess_and_runner_has_no_torch_context() -> None:
    fixture_text = runner.FIXTURE.read_text()
    runner_text = runner.RUNNER.read_text()
    assert "import subprocess" not in fixture_text
    assert "subprocess." not in fixture_text
    assert "collect_runtime_identity" not in fixture_text
    assert "platform.platform" not in fixture_text
    assert "import torch" not in runner_text
    assert "torch.xpu" not in runner_text


def test_local_nvme_and_password_metadata_preflights() -> None:
    assert runner.local_nvme_mount_identity() == {
        "target": "/mnt/fast-ai",
        "mount_point": "/",
        "source": "/dev/nvme0n1p2",
        "filesystem": "ext4",
    }
    password = runner.verify_sudo_password_file()
    assert password["mode"] == "0600"
    assert password["content_not_recorded"] is True
