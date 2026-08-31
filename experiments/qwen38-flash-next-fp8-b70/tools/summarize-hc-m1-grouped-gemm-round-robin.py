#!/usr/bin/env python3
"""Apply the frozen two-process 97-weight HC grouped-GEMM family gate."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics


BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
OUTPUT = BASE / "hc-m1-grouped-up-round-robin-summary-seed20260831.json"
RUN_TOOL = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm-round-robin.py")
RUN_TOOL_SHA256 = "7199b1c070abb4fdbb1a62ad92c4caed4ef5d2b1c9e3f80feaaf91af8fc7572b"
CORE_TOOL = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")
CORE_SHA256 = "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
PAIR_DRIVER = Path(__file__).with_name("run-hc-m1-grouped-gemm-pair.py")
PAIR_DRIVER_SHA256 = "650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7"
AUTHORITY = BASE / "hc-m1-grouped-up-round-robin-authority-seed20260831.json"
AUTHORITY_SHA256 = "15af5344c259fa83ffc16ca1755c621a83cce01651119b2c5234c4276a2fcab9"
MODEL = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
WEIGHT_MANIFEST_SHA256 = (
    "da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7"
)
AUTHORITY_MANIFEST_SHA256 = (
    "78d773b0a4387e2396828c3b360983ab79051f871065377aaf8dba3ef3b1c91e"
)
AUTHORITY_SWEEP_SHA256 = (
    "cbe21f41db001fd54b8b84f782c0a39f894fdc8fa92677fb12e87500e683c5f7"
)
INPUT_DEVICE_MANIFEST_SHA256 = (
    "0cc7b0522f32e6feda641c1e82ff920943251aa750b62f74da0d1d469c3a3db3"
)
LINEAR_DEVICE_MANIFEST_SHA256 = (
    "875f289c2b33e718ee32c2818fb854afa5855472414f1592f93613a3f6576b63"
)
ROWS_PER_EXPERT_SHA256 = (
    "67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450"
)
NORMALIZED_LOADER_SHA256 = (
    "ce2247ccad4f7466ad69dfc9469d9adc5fa41ebe89ac4016570bae9d5e4680c4"
)
STAGE = "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
STAGE_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
RUNTIME_MANIFEST = {
    "_xpu_C.abi3.so": "07cba22dbfef80914784767a556320df87215b2ebc1226716da9d775a3c66dc3",
    "libgrouped_gemm_xe_2.so": (
        "4493c3030b1a53b756953c15e390b740023ee68f16ca8783cb0a5213600f1ac8"
    ),
}
PROCESS_GATE = {
    "median_reduction_minimum_percent": 50.0,
    "every_cycle_reduction_minimum_percent": 20.0,
    "median_saving_minimum_ms": 0.75,
    "order_bias_maximum_points": 10.0,
}
FAMILY_GATE = {
    "processes_required": 2,
    "median_reduction_spread_maximum_points": 10.0,
    "median_saving_spread_maximum_ms": 0.5,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def verify_evidence_mount() -> dict[str, object]:
    mounts = []
    for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
        source, target, filesystem, *_ = line.split()
        if target == "/mnt/usb-models":
            mounts.append((source, filesystem))
    if mounts != [("/dev/sda2", "fuseblk")]:
        raise RuntimeError(f"unexpected evidence mount identity: {mounts}")
    stat = os.statvfs(BASE)
    free_bytes = stat.f_bavail * stat.f_frsize
    if free_bytes < 100 * 1024**3:
        raise RuntimeError(f"insufficient evidence-drive free space: {free_bytes}")
    return {
        "source": mounts[0][0],
        "filesystem": mounts[0][1],
        "mount": "/mnt/usb-models",
        "free_bytes": free_bytes,
        "minimum_free_bytes": 100 * 1024**3,
    }


def normalized_loader_sha256(lines: object) -> str:
    if (
        not isinstance(lines, list)
        or not lines
        or not all(isinstance(line, str) for line in lines)
    ):
        raise RuntimeError("runtime loader closure is missing")
    normalized = [re.sub(r"\s+\(0x[0-9a-f]+\)$", "", line) for line in lines]
    joined = "\n".join(normalized)
    if (
        f"{STAGE}/libgrouped_gemm_xe_2.so" not in joined
        or "/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8" not in joined
    ):
        raise RuntimeError("runtime loader closure omits frozen providers")
    return canonical_sha256(normalized)


def validate_process(path: Path, repeat: str, authority: dict[str, object]) -> dict:
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    expected = {
        "schema_version": 1,
        "classification": "production_order_97_weight_round_robin_component_gate",
        "repeat": repeat,
        "evidence_path": str(path),
        "model": MODEL,
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "production_order": "layer0-attn,layer0-mlp,...,layer47-attn,layer47-mlp,final",
        "mtp_weights_included": False,
        "weight_count": 97,
        "weight_bank_bytes": 635699200,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_evidence": str(AUTHORITY),
        "authority_evidence_sha256": AUTHORITY_SHA256,
        "authority_manifest_sha256": AUTHORITY_MANIFEST_SHA256,
        "authority_sweep_sha256": AUTHORITY_SWEEP_SHA256,
        "seed": 20260831,
        "shape": {"m": 1, "n": 10240, "k": 320},
        "dtype": "torch.bfloat16",
        "candidate_output_allocation": "fresh torch.empty per production slot call",
        "candidate_batching": "97 sequential E=1 calls; never E=97",
        "runtime_stage": STAGE,
        "runtime_manifest": RUNTIME_MANIFEST,
        "runtime_manifest_sha256": STAGE_MANIFEST_SHA256,
        "library_sha256": RUNTIME_MANIFEST["_xpu_C.abi3.so"],
        "normalized_loader_sha256": NORMALIZED_LOADER_SHA256,
        "repeats": {
            "warmup_sweeps_per_provider": 100,
            "cycles": 31,
            "sweeps_per_provider_per_cycle": 100,
            "exactness_sweeps_per_provider": 100,
        },
        "all_97_outputs_exact_and_finite": True,
        "unique_aggregate_output_sha256": 1,
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
        "tool_sha256": RUN_TOOL_SHA256,
        "core_sha256": CORE_SHA256,
        "pair_driver_sha256": PAIR_DRIVER_SHA256,
    }
    for field, value in expected.items():
        if raw.get(field) != value:
            raise RuntimeError(f"{path}: identity mismatch for {field}")
    if raw.get("gate") != {**PROCESS_GATE, "passed": raw.get("process_gate_passed")}:
        raise RuntimeError(f"{path}: process-gate identity mismatch")
    device = raw.get("device")
    if (
        not isinstance(device, dict)
        or device.get("selector") != "level_zero:0"
        or device.get("count") != 1
        or "Arc" not in str(device.get("name"))
        or "B70" not in str(device.get("name"))
        or device.get("torch") != "2.11.0+xpu"
    ):
        raise RuntimeError(f"{path}: device identity mismatch")
    sycl = raw.get("sycl_identity")
    if (
        not isinstance(sycl, dict)
        or sycl.get("sha256")
        != "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
    ):
        raise RuntimeError(f"{path}: SYCL provider identity mismatch")
    process = raw.get("process_identity")
    if (
        not isinstance(process, dict)
        or not isinstance(process.get("boot_id"), str)
        or len(process["boot_id"]) != 36
        or not isinstance(process.get("pid"), int)
        or process["pid"] <= 0
        or not isinstance(process.get("process_start_ticks"), int)
        or process["process_start_ticks"] <= 0
        or not isinstance(process.get("nonce"), str)
        or len(process["nonce"]) != 64
    ):
        raise RuntimeError(f"{path}: invalid process identity")

    slot_identities = raw.get("slot_identities")
    authority_weights = authority.get("weight_manifest")
    authority_outputs = authority.get("authorities")
    if (
        not isinstance(slot_identities, list)
        or len(slot_identities) != 97
        or not isinstance(authority_weights, list)
        or not isinstance(authority_outputs, list)
    ):
        raise RuntimeError(f"{path}: slot identities are incomplete")
    output_by_slot = {item[0]: item[1:] for item in authority_outputs}
    reconstructed_weights = []
    reconstructed_authorities = []
    for slot, authority_weight in zip(slot_identities, authority_weights):
        expected_slot = {
            **authority_weight,
            "input_sha256": output_by_slot[authority_weight["slot"]][0],
            "authority_output_sha256": output_by_slot[authority_weight["slot"]][1],
        }
        if slot != expected_slot:
            raise RuntimeError(
                f"{path}: slot binding mismatch for {authority_weight['slot']}"
            )
        reconstructed_weights.append(authority_weight)
        reconstructed_authorities.append(
            [
                authority_weight["slot"],
                slot["input_sha256"],
                slot["authority_output_sha256"],
            ]
        )
    if canonical_sha256(reconstructed_weights) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError(f"{path}: reconstructed weight manifest mismatch")
    if canonical_sha256(reconstructed_authorities) != AUTHORITY_MANIFEST_SHA256:
        raise RuntimeError(f"{path}: reconstructed authority manifest mismatch")

    cycles = raw.get("cycles")
    if not isinstance(cycles, list) or len(cycles) != 31:
        raise RuntimeError(f"{path}: cycle count mismatch")
    reductions: list[float] = []
    savings: list[float] = []
    linear_times: list[float] = []
    grouped_times: list[float] = []
    linear_first: list[float] = []
    grouped_first: list[float] = []
    aggregate_hashes: set[str] = set()
    for index, cycle in enumerate(cycles):
        expected_order = "linear_grouped" if index % 2 == 0 else "grouped_linear"
        if cycle.get("cycle") != index or cycle.get("order") != expected_order:
            raise RuntimeError(f"{path}: cycle order mismatch at {index}")
        linear_ms = float(cycle["linear_full_97_sweep_ms"])
        grouped_ms = float(cycle["grouped_full_97_sweep_ms"])
        saving = float(cycle["saving_ms"])
        reduction = float(cycle["latency_reduction_percent"])
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in (linear_ms, grouped_ms)
        ):
            raise RuntimeError(f"{path}: invalid timing at cycle {index}")
        if not close(saving, linear_ms - grouped_ms):
            raise RuntimeError(f"{path}: saving mismatch at cycle {index}")
        if not close(reduction, saving / linear_ms * 100.0):
            raise RuntimeError(f"{path}: reduction mismatch at cycle {index}")
        reductions.append(reduction)
        savings.append(saving)
        linear_times.append(linear_ms)
        grouped_times.append(grouped_ms)
        aggregate_hashes.add(str(cycle["aggregate_output_sha256"]))
        (linear_first if expected_order == "linear_grouped" else grouped_first).append(
            reduction
        )
    if aggregate_hashes != {AUTHORITY_SWEEP_SHA256}:
        raise RuntimeError(f"{path}: cycle authority hash mismatch")
    median_reduction = statistics.median(reductions)
    minimum_reduction = min(reductions)
    median_saving = statistics.median(savings)
    order_bias = abs(statistics.median(linear_first) - statistics.median(grouped_first))
    summaries = {
        "linear_full_97_sweep_ms": linear_times,
        "grouped_full_97_sweep_ms": grouped_times,
        "saving_ms": savings,
        "latency_reduction_percent": reductions,
    }
    for field, values in summaries.items():
        summary = raw.get(field)
        if not isinstance(summary, dict):
            raise RuntimeError(f"{path}: missing summary {field}")
        if not close(float(summary["median"]), statistics.median(values)):
            raise RuntimeError(f"{path}: median mismatch for {field}")
    if not close(float(raw["saving_ms"]["minimum"]), min(savings)):
        raise RuntimeError(f"{path}: minimum saving mismatch")
    if not close(float(raw["latency_reduction_percent"]["minimum"]), minimum_reduction):
        raise RuntimeError(f"{path}: minimum reduction mismatch")
    if not close(float(raw["order_bias_points"]), order_bias):
        raise RuntimeError(f"{path}: order bias mismatch")
    passed = (
        median_reduction >= PROCESS_GATE["median_reduction_minimum_percent"]
        and minimum_reduction >= PROCESS_GATE["every_cycle_reduction_minimum_percent"]
        and median_saving >= PROCESS_GATE["median_saving_minimum_ms"]
        and order_bias <= PROCESS_GATE["order_bias_maximum_points"]
    )
    if raw.get("process_gate_passed") is not passed:
        raise RuntimeError(f"{path}: process decision mismatch")
    expected_status = "process_gate_passed" if passed else "process_gate_failed"
    if raw.get("status") != expected_status:
        raise RuntimeError(f"{path}: process status mismatch")
    memory = raw.get("memory")
    if (
        not isinstance(memory, dict)
        or memory.get("duplicate_steady_bank_is_endpoint_eligible") is not False
        or int(memory.get("linear_bank_delta_bytes", 0)) < 635699200
        or int(memory.get("packed_bank_delta_bytes", 0)) < 635699200
    ):
        raise RuntimeError(f"{path}: duplicate-bank memory disclosure mismatch")
    for host_field in ("host_preflight", "host_postflight"):
        host = raw.get(host_field)
        if (
            not isinstance(host, dict)
            or host.get("evidence_source") != "/dev/sda2"
            or host.get("evidence_filesystem") != "fuseblk"
            or host.get("evidence_mount") != "/mnt/usb-models"
            or host.get("model_on_root_nvme_device") is not True
            or int(host.get("evidence_free_bytes", 0)) < 100 * 1024**3
            or int(host.get("mem_available_bytes", 0)) < 100 * 1024**3
            or int(host.get("swap_free_bytes", 0)) < 7 * 1024**3
        ):
            raise RuntimeError(f"{path}: {host_field} disclosure mismatch")
    device_state = raw.get("device_state_manifests")
    if (
        not isinstance(device_state, dict)
        or device_state.get("all_unchanged_after_candidate") is not True
        or not all(
            isinstance(device_state.get(field), str) and len(device_state[field]) == 64
            for field in (
                "input_bank_sha256",
                "linear_weight_bank_sha256",
                "packed_weight_bank_sha256",
                "rows_per_expert_sha256",
            )
        )
        or device_state["input_bank_sha256"] != INPUT_DEVICE_MANIFEST_SHA256
        or device_state["linear_weight_bank_sha256"] != LINEAR_DEVICE_MANIFEST_SHA256
        or device_state["rows_per_expert_sha256"] != ROWS_PER_EXPERT_SHA256
        or device_state["packed_weight_bank_sha256"]
        != raw["startup"]["packed_manifest_sha256"]
    ):
        raise RuntimeError(f"{path}: device-state manifest mismatch")
    runpaths = raw.get("runpath_evidence")
    if not isinstance(runpaths, dict) or set(runpaths) != set(RUNTIME_MANIFEST):
        raise RuntimeError(f"{path}: runtime RUNPATH receipt mismatch")
    for library_name, entries in runpaths.items():
        if (
            not isinstance(entries, list)
            or not entries
            or not any("Library runpath: [$ORIGIN]" in entry for entry in entries)
        ):
            raise RuntimeError(f"{path}: missing $ORIGIN RUNPATH for {library_name}")
    normalized_loader_digest = normalized_loader_sha256(raw.get("loader_closure"))
    if normalized_loader_digest != NORMALIZED_LOADER_SHA256:
        raise RuntimeError(f"{path}: normalized loader closure mismatch")
    if not close(
        float(raw["linear_full_97_sweep_ms"]["median_per_call_us"]),
        statistics.median(linear_times) * 1000.0 / 97,
    ):
        raise RuntimeError(f"{path}: linear per-call derivation mismatch")
    if not close(
        float(raw["grouped_full_97_sweep_ms"]["median_per_call_us"]),
        statistics.median(grouped_times) * 1000.0 / 97,
    ):
        raise RuntimeError(f"{path}: grouped per-call derivation mismatch")
    return {
        "repeat": repeat,
        "path": str(path),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "process_identity": process,
        "passed": passed,
        "median_linear_full_97_sweep_ms": statistics.median(linear_times),
        "median_grouped_full_97_sweep_ms": statistics.median(grouped_times),
        "median_saving_ms": median_saving,
        "median_reduction_percent": median_reduction,
        "minimum_reduction_percent": minimum_reduction,
        "order_bias_points": order_bias,
        "packed_manifest_sha256": raw["startup"]["packed_manifest_sha256"],
        "prepack_seconds": raw["startup"]["prepack_seconds"],
        "memory": memory,
        "all_97_outputs_exact_and_finite": True,
        "device_state_manifests": device_state,
        "normalized_loader_sha256": normalized_loader_digest,
        "runpath_evidence": runpaths,
    }


def main() -> None:
    tool = Path(__file__).resolve()
    tool_sha256 = sha256(tool)
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite aggregate evidence: {OUTPUT}")
    expected_tools = {
        RUN_TOOL: RUN_TOOL_SHA256,
        CORE_TOOL: CORE_SHA256,
        PAIR_DRIVER: PAIR_DRIVER_SHA256,
    }
    for path, expected in expected_tools.items():
        if sha256(path) != expected:
            raise RuntimeError(f"tool identity drift: {path}")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("authority evidence digest drift")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if canonical_sha256(authority["weight_manifest"]) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("authority weight manifest drift")
    if canonical_sha256(authority["authorities"]) != AUTHORITY_MANIFEST_SHA256:
        raise RuntimeError("authority output manifest drift")

    runs = [
        validate_process(
            BASE / f"hc-m1-grouped-up-round-robin-{repeat}-seed20260831.json",
            repeat,
            authority,
        )
        for repeat in ("r1", "r2")
    ]
    process_instances = {
        (
            run["process_identity"]["boot_id"],
            run["process_identity"]["pid"],
            run["process_identity"]["process_start_ticks"],
        )
        for run in runs
    }
    nonces = {run["process_identity"]["nonce"] for run in runs}
    packed_manifests = {run["packed_manifest_sha256"] for run in runs}
    device_manifests = {
        tuple(sorted(run["device_state_manifests"].items())) for run in runs
    }
    loader_closures = {run["normalized_loader_sha256"] for run in runs}
    runpath_evidence = {
        json.dumps(run["runpath_evidence"], sort_keys=True) for run in runs
    }
    reduction_spread = abs(
        runs[0]["median_reduction_percent"] - runs[1]["median_reduction_percent"]
    )
    saving_spread = abs(runs[0]["median_saving_ms"] - runs[1]["median_saving_ms"])
    passed = (
        all(run["passed"] for run in runs)
        and len(process_instances) == 2
        and len(nonces) == 2
        and len(packed_manifests) == 1
        and len(device_manifests) == 1
        and len(loader_closures) == 1
        and len(runpath_evidence) == 1
        and reduction_spread <= FAMILY_GATE["median_reduction_spread_maximum_points"]
        and saving_spread <= FAMILY_GATE["median_saving_spread_maximum_ms"]
    )
    median_component_saving = statistics.median(
        [run["median_saving_ms"] for run in runs]
    )
    result = {
        "schema_version": 1,
        "status": "family_gate_passed" if passed else "family_gate_failed",
        "classification": "two_process_97_weight_round_robin_component_gate",
        "runs": runs,
        "authority_evidence": str(AUTHORITY),
        "authority_evidence_sha256": AUTHORITY_SHA256,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_manifest_sha256": AUTHORITY_MANIFEST_SHA256,
        "process_gate": PROCESS_GATE,
        "family_gate": FAMILY_GATE,
        "family_observed": {
            "distinct_process_instances": len(process_instances),
            "distinct_nonces": len(nonces),
            "distinct_packed_manifests": len(packed_manifests),
            "distinct_device_state_manifests": len(device_manifests),
            "distinct_loader_closures": len(loader_closures),
            "distinct_runpath_receipts": len(runpath_evidence),
            "median_reduction_spread_points": reduction_spread,
            "median_saving_spread_ms": saving_spread,
            "median_component_saving_ms": median_component_saving,
        },
        "all_97_outputs_exact_and_finite": all(
            run["all_97_outputs_exact_and_finite"] for run in runs
        ),
        "source_integration_candidate_authorized": passed,
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
        "duplicate_packed_bank_endpoint_eligible": False,
        "integration_requirement": (
            "replace or release the original 635699200-byte HC-up bank; "
            "do not retain duplicate linear and packed banks per card"
        ),
        "tool_sha256": RUN_TOOL_SHA256,
        "core_sha256": CORE_SHA256,
        "pair_driver_sha256": PAIR_DRIVER_SHA256,
        "aggregate_tool_sha256": tool_sha256,
    }
    for path, expected in expected_tools.items():
        if sha256(path) != expected:
            raise RuntimeError(f"tool changed before aggregate write: {path}")
    if sha256(tool) != tool_sha256 or sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("aggregate closure changed before write")
    for run in runs:
        if sha256(Path(run["path"])) != run["sha256"]:
            raise RuntimeError(f"validated evidence changed: {run['path']}")
    aggregate_mount_preflight = verify_evidence_mount()
    result["aggregate_mount_preflight"] = aggregate_mount_preflight
    nonce = os.urandom(32).hex()
    temporary = OUTPUT.with_name(f"{OUTPUT.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        verify_evidence_mount()
        os.link(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
