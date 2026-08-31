#!/usr/bin/env python3
"""Orchestrate the frozen all-97 M64 and sentinel-wide HC fallback gate."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time


MODEL = Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
WEIGHT_MANIFEST_SHA256 = (
    "da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7"
)
AUTHORITY = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "hc-m1-grouped-up-round-robin-authority-seed20260831.json"
)
AUTHORITY_SHA256 = "15af5344c259fa83ffc16ca1755c621a83cce01651119b2c5234c4276a2fcab9"
WORKER = Path(__file__).with_name("benchmark-hc-up-mgt1-packed-fallback.py")
WORKER_SHA256 = "153a51f4a742f461f6bd1a5d4e4e289ca2f91415d11f66e65580d1221d2891c4"
WORKER_PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
STAGE = Path(
    "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
)
STAGE_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
SEED = 20260831
RUN_ATTEMPT = 2
M_VALUES = (2, 8, 64, 256, 1024, 4096)
PROVIDERS = ("authority", "packed_view", "matmul", "grouped")
SENTINELS = ("00-attn", "00-mlp", "24-attn", "47-mlp", "final")
LOCK_PATHS = (
    Path("/tmp/q38-hc-up-mgt1-gate-driver.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-round-robin.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-alternating.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-pair.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm.lock"),
)
MIN_HOST_AVAILABLE_BYTES = 8 * 1024**3
MIN_SWAP_FREE_BYTES = 4 * 1024**3
MIN_EVIDENCE_FREE_BYTES = 50 * 1024**3
LOADER_SUFFIX = (
    "/home/steve/.venvs/vllm-xpu/lib",
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
    "/opt/intel/oneapi/compiler/2025.3/lib",
    "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def production_slots() -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    for layer in range(48):
        for family in ("attn", "mlp"):
            slots.append(
                (
                    f"{layer:02d}-{family}",
                    "model.language_model.layers."
                    f"{layer}.{family}_hyper_connection."
                    "input_mix_weight_up.weight",
                )
            )
    slots.append(
        (
            "final",
            "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight",
        )
    )
    return slots


def cells(scope: str) -> list[tuple[str, int]]:
    if scope == "smoke":
        return [("00-attn", 2)]
    if scope == "s1":
        return [("00-attn", 2), ("00-attn", 64)]
    if scope == "s2":
        return [(slot, m) for m in M_VALUES for slot in SENTINELS]
    if scope == "s3":
        return [(slot, 64) for slot, _ in production_slots()]
    raise RuntimeError(f"unknown gate scope: {scope}")


def plan(scope: str) -> dict[str, object]:
    arm_plan = [
        {
            "slot": slot,
            "m": m,
            "provider": provider,
            "output_name": f"{slot}-m{m}-{provider}.json",
        }
        for slot, m in cells(scope)
        for provider in PROVIDERS
    ]
    expected_arms = {"smoke": 4, "s1": 8, "s2": 120, "s3": 388}[scope]
    if len(arm_plan) != expected_arms:
        raise RuntimeError(f"frozen {scope} arm plan is not {expected_arms} entries")
    return {
        "schema_version": 1,
        "classification": "source_only_hc_up_mgt1_packed_fallback_plan",
        "scope": scope,
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "seed": SEED,
        "run_attempt": RUN_ATTEMPT,
        "worker_python": str(WORKER_PYTHON),
        "all_97_m64": scope == "s3",
        "sentinels": list(SENTINELS) if scope == "s2" else ["00-attn"],
        "sentinel_m_values": (
            list(M_VALUES)
            if scope == "s2"
            else ([2, 64] if scope == "s1" else [2] if scope == "smoke" else [64])
        ),
        "providers": list(PROVIDERS),
        "cell_count": len(cells(scope)),
        "arm_count": len(arm_plan),
        "arms": arm_plan,
    }


def atomic_write_json(path: Path, value: object, nonce: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        verify_host_and_storage()
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, value: str, nonce: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        verify_host_and_storage()
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        name, raw = line.split(":", maxsplit=1)
        values[name] = int(raw.strip().split()[0]) * 1024
    return values


def verify_host_and_storage() -> dict[str, object]:
    mounts = []
    for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
        source, target, filesystem, options, *_ = line.split()
        if target == "/mnt/usb-models":
            mounts.append((source, filesystem, options))
    if len(mounts) != 1 or mounts[0][0:2] != ("/dev/sda2", "fuseblk"):
        raise RuntimeError(f"unexpected evidence mount identity: {mounts}")
    if os.stat(MODEL).st_dev != os.stat("/").st_dev:
        raise RuntimeError("active checkpoint is not on the local root/NVMe device")
    evidence_stat = os.statvfs(EVIDENCE_BASE)
    evidence_free = evidence_stat.f_bavail * evidence_stat.f_frsize
    if evidence_free < MIN_EVIDENCE_FREE_BYTES:
        raise RuntimeError(f"insufficient evidence-drive free space: {evidence_free}")
    memory = read_meminfo()
    if memory["MemAvailable"] < MIN_HOST_AVAILABLE_BYTES:
        raise RuntimeError(f"insufficient host memory: {memory['MemAvailable']}")
    if memory["SwapFree"] < MIN_SWAP_FREE_BYTES:
        raise RuntimeError(f"insufficient free swap: {memory['SwapFree']}")
    return {
        "evidence_source": mounts[0][0],
        "evidence_filesystem": mounts[0][1],
        "evidence_mount": "/mnt/usb-models",
        "evidence_free_bytes": evidence_free,
        "model_on_root_nvme_device": True,
        "mem_available_bytes": memory["MemAvailable"],
        "swap_free_bytes": memory["SwapFree"],
        "minimums": {
            "evidence_free_bytes": MIN_EVIDENCE_FREE_BYTES,
            "mem_available_bytes": MIN_HOST_AVAILABLE_BYTES,
            "swap_free_bytes": MIN_SWAP_FREE_BYTES,
        },
    }


def refuse_render_node_owners() -> None:
    own_pid = os.getpid()
    owners: list[tuple[int, str]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == own_pid:
            continue
        try:
            for descriptor in (proc / "fd").iterdir():
                try:
                    target = os.readlink(descriptor)
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
                if target.startswith("/dev/dri/renderD"):
                    owners.append((int(proc.name), target))
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if owners:
        raise RuntimeError(f"another process owns a render node: {owners}")


def refuse_active_server() -> None:
    needles = (
        b"vllm serve",
        b"vllm.entrypoints.openai.api_server",
        b"VLLM::Engine",
        b"VLLM::Worker",
        b"qwen38-flash-next-fp8-tp",
    )
    own_pid = os.getpid()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == own_pid:
            continue
        try:
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ")
            comm = (proc / "comm").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(needle in command + b" " + comm for needle in needles):
            raise RuntimeError(f"active model/server process detected: pid {proc.name}")


def verify_authority() -> dict[str, object]:
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("97-weight authority evidence digest drift")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    expected = {
        "status": "production_authority_frozen",
        "classification": "control_only_97_weight_round_robin_census",
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "weight_count": 97,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "candidate_invocations": 0,
    }
    for field, value in expected.items():
        if authority.get(field) != value:
            raise RuntimeError(f"authority identity mismatch for {field}")
    manifest = authority.get("weight_manifest")
    if not isinstance(manifest, list) or len(manifest) != 97:
        raise RuntimeError("authority weight manifest is incomplete")
    if canonical_sha256(manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("authority weight manifest content drift")
    observed = [(item.get("slot"), item.get("name")) for item in manifest]
    if observed != production_slots():
        raise RuntimeError("authority production order or scope drift")
    return authority


def validate_cell(arms: list[dict[str, object]], slot: str, m: int) -> dict[str, bool]:
    if [arm.get("provider") for arm in arms] != list(PROVIDERS):
        raise RuntimeError(f"provider sequence drift for {slot} M={m}")
    identity_fields = (
        "repeat",
        "scope",
        "run_attempt",
        "slot",
        "slot_index",
        "weight_name",
        "model_shard",
        "model",
        "model_revision",
        "model_index_sha256",
        "model_config_sha256",
        "weight_manifest_sha256",
        "authority_evidence",
        "authority_evidence_sha256",
        "shape",
        "dtype",
        "seed",
        "cell_seed",
        "input_sha256",
        "logical_weight_sha256",
        "runtime_stage",
        "runtime_manifest",
        "runtime_manifest_sha256",
        "device",
    )
    for field in identity_fields:
        values = {json.dumps(arm.get(field), sort_keys=True) for arm in arms}
        if len(values) != 1:
            raise RuntimeError(f"cell identity mismatch for {slot} M={m}: {field}")
    for arm in arms:
        if arm.get("status") != "component_arm_valid":
            raise RuntimeError(f"invalid arm status for {slot} M={m}")
        if arm.get("scope") not in ("smoke", "s1", "s2", "s3"):
            raise RuntimeError(f"invalid arm scope for {slot} M={m}")
        if arm.get("slot") != slot or arm.get("shape", {}).get("m") != m:
            raise RuntimeError(f"arm selection drift for {slot} M={m}")
        if arm.get("unique_output_sha256") != 1 or not arm.get("finite"):
            raise RuntimeError(f"arm correctness failure for {slot} M={m}")
        if not arm.get("fresh_output_allocation"):
            raise RuntimeError(f"arm reused a live output for {slot} M={m}")
        if arm.get("source_integration_authorized") is not False:
            raise RuntimeError("an individual arm claimed integration authority")
    authority_hash = arms[0].get("output_sha256")
    return {
        str(arm["provider"]): arm.get("output_sha256") == authority_hash for arm in arms
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--scope", choices=("smoke", "s1", "s2", "s3"), default="smoke")
    parser.add_argument("--repeat", choices=("r1", "r2"))
    args = parser.parse_args()

    script = Path(__file__).resolve()
    script_sha256 = sha256(script)
    if sha256(WORKER) != WORKER_SHA256:
        raise RuntimeError("frozen M>1 worker has drifted")
    frozen_plan = plan(args.scope)
    frozen_plan["worker_sha256"] = WORKER_SHA256
    frozen_plan["driver_sha256"] = script_sha256
    frozen_plan["plan_sha256"] = canonical_sha256(plan(args.scope))
    if args.source_only:
        if args.repeat is not None:
            raise RuntimeError("--source-only does not accept --repeat")
        print(json.dumps(frozen_plan, indent=2, sort_keys=True))
        return
    if args.scope == "smoke":
        if args.repeat is not None:
            raise RuntimeError("smoke uses a distinct unlabeled evidence path")
        run_name = f"hc-up-mgt1-packed-fallback-smoke-a{RUN_ATTEMPT}-seed{SEED}"
    else:
        if args.repeat is None:
            raise RuntimeError("staged scopes require --repeat r1 or r2")
        run_name = (
            f"hc-up-mgt1-packed-fallback-{args.scope}-{args.repeat}-"
            f"a{RUN_ATTEMPT}-seed{SEED}"
        )

    locks = []
    for lock_path in LOCK_PATHS:
        lock = lock_path.open("w", encoding="utf-8")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"component lock is held: {lock_path}") from error
        locks.append(lock)
    refuse_active_server()
    refuse_render_node_owners()
    host_preflight = verify_host_and_storage()
    authority = verify_authority()
    if sha256(STAGE / "SHA256SUMS") != STAGE_MANIFEST_SHA256:
        raise RuntimeError("runtime-stage manifest digest drift")
    if sha256(MODEL / "model.safetensors.index.json") != MODEL_INDEX_SHA256:
        raise RuntimeError("model index digest drift")
    if sha256(MODEL / "config.json") != MODEL_CONFIG_SHA256:
        raise RuntimeError("model config digest drift")
    if not WORKER_PYTHON.is_file() or not os.access(WORKER_PYTHON, os.X_OK):
        raise RuntimeError(f"frozen worker Python is unavailable: {WORKER_PYTHON}")

    run_dir = EVIDENCE_BASE / run_name
    arms_dir = run_dir / "arms"
    streams_dir = run_dir / "streams"
    receipts_dir = run_dir / "receipts"
    summary_path = run_dir / "summary.json"
    if run_dir.exists():
        raise RuntimeError(f"refusing to reuse an evidence directory: {run_dir}")
    arms_dir.mkdir(parents=True, exist_ok=False)
    streams_dir.mkdir()
    receipts_dir.mkdir()
    driver_nonce = secrets.token_hex(32)
    driver_nonce_sha256 = hashlib.sha256(driver_nonce.encode()).hexdigest()
    environment = os.environ.copy()
    environment["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["LD_LIBRARY_PATH"] = ":".join((str(STAGE), *LOADER_SUFFIX))
    environment["Q38_HC_MGT1_DRIVER_PID"] = str(os.getpid())
    environment["Q38_HC_MGT1_DRIVER_NONCE"] = driver_nonce

    validated_cells: list[dict[str, object]] = []
    arm_closure: list[tuple[Path, str]] = []
    exact_counts = {provider: 0 for provider in PROVIDERS}
    mismatches = {provider: [] for provider in PROVIDERS}
    for slot, m in cells(args.scope):
        cell_arms: list[dict[str, object]] = []
        for provider in PROVIDERS:
            if sha256(script) != script_sha256 or sha256(WORKER) != WORKER_SHA256:
                raise RuntimeError("driver/worker closure changed before an arm")
            output = arms_dir / f"{slot}-m{m}-{provider}.json"
            stdout_path = streams_dir / f"{slot}-m{m}-{provider}.stdout.txt"
            stderr_path = streams_dir / f"{slot}-m{m}-{provider}.stderr.txt"
            receipt_path = receipts_dir / f"{slot}-m{m}-{provider}.json"
            command = [
                str(WORKER_PYTHON),
                str(WORKER),
                "--scope",
                args.scope,
                "--slot",
                slot,
                "--m",
                str(m),
                "--provider",
                provider,
                "--output",
                str(output),
            ]
            if args.repeat is not None:
                command[4:4] = ["--repeat", args.repeat]
            started = time.time_ns()
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            stdout, stderr = process.communicate()
            ended = time.time_ns()
            receipt_nonce = secrets.token_hex(32)
            atomic_write_text(stdout_path, stdout, receipt_nonce)
            atomic_write_text(stderr_path, stderr, receipt_nonce)
            receipt = {
                "schema_version": 1,
                "scope": args.scope,
                "repeat": args.repeat,
                "run_attempt": RUN_ATTEMPT,
                "slot": slot,
                "m": m,
                "provider": provider,
                "command": command,
                "pid": process.pid,
                "parent_pid": os.getpid(),
                "driver_nonce_sha256": driver_nonce_sha256,
                "started_time_ns": started,
                "ended_time_ns": ended,
                "returncode": process.returncode,
                "stdout_path": str(stdout_path),
                "stdout_sha256": sha256(stdout_path),
                "stderr_path": str(stderr_path),
                "stderr_sha256": sha256(stderr_path),
                "arm_path": str(output),
                "arm_exists": output.is_file(),
                "arm_sha256": sha256(output) if output.is_file() else None,
            }
            atomic_write_json(receipt_path, receipt, receipt_nonce)
            if process.returncode != 0:
                raise RuntimeError(
                    f"arm failed for {slot} M={m} {provider} rc={process.returncode}; "
                    f"receipt={receipt_path}: {stderr[-4000:]}"
                )
            if not output.is_file():
                raise RuntimeError(f"worker omitted evidence: {output}")
            arm = json.loads(output.read_text(encoding="utf-8"))
            if arm.get("tool_sha256") != WORKER_SHA256:
                raise RuntimeError(f"worker identity drift in {output}")
            if arm.get("scope") != args.scope or arm.get("repeat") != args.repeat:
                raise RuntimeError(f"worker run identity drift in {output}")
            process_identity = arm.get("process_identity")
            if (
                not isinstance(process_identity, dict)
                or process_identity.get("pid") != process.pid
                or process_identity.get("parent_pid") != os.getpid()
                or process_identity.get("driver_nonce_sha256") != driver_nonce_sha256
            ):
                raise RuntimeError(f"worker process binding drift in {output}")
            if arm.get("loader_closure_before") != arm.get("loader_closure_after"):
                raise RuntimeError(f"loader closure changed in {output}")
            loader = arm.get("loader_closure_before")
            if (
                not isinstance(loader, dict)
                or loader.get("normalized_sha256")
                != "ce2247ccad4f7466ad69dfc9469d9adc5fa41ebe89ac4016570bae9d5e4680c4"
            ):
                # Keep a literal comparison here so a worker-only constant edit
                # cannot weaken the driver's independent closure check.
                raise RuntimeError(f"loader closure identity drift in {output}")
            arm_sha256 = sha256(output)
            if receipt["arm_sha256"] != arm_sha256:
                raise RuntimeError(f"arm changed after process receipt: {output}")
            arm_closure.append((output, arm_sha256))
            cell_arms.append(arm)
        exact_to_authority = validate_cell(cell_arms, slot, m)
        for provider, exact in exact_to_authority.items():
            if exact:
                exact_counts[provider] += 1
            else:
                mismatches[provider].append({"slot": slot, "m": m})
        validated_cells.append(
            {
                "slot": slot,
                "m": m,
                "output_sha256": cell_arms[0]["output_sha256"],
                "arms": [
                    {
                        "provider": arm["provider"],
                        "path": str(arms_dir / f"{slot}-m{m}-{arm['provider']}.json"),
                        "sha256": sha256(
                            arms_dir / f"{slot}-m{m}-{arm['provider']}.json"
                        ),
                        "median_us": arm["timing_us"]["median"],
                        "exact_to_authority": exact_to_authority[str(arm["provider"])],
                    }
                    for arm in cell_arms
                ],
            }
        )

    if len(validated_cells) != len(cells(args.scope)):
        raise RuntimeError("validated cell count drift")
    for path, expected_digest in arm_closure:
        if sha256(path) != expected_digest:
            raise RuntimeError(f"arm changed before summary closure: {path}")
    summary_nonce = secrets.token_hex(32)
    all_exact = all(not entries for entries in mismatches.values())
    summary = {
        "schema_version": 1,
        "status": "component_matrix_classified",
        "classification": "real_weight_hc_up_mgt1_packed_fallback_gate",
        "scope": args.scope,
        "repeat": args.repeat,
        "run_attempt": RUN_ATTEMPT,
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_evidence": str(AUTHORITY),
        "authority_evidence_sha256": AUTHORITY_SHA256,
        "authority_weight_count": len(authority["weight_manifest"]),
        "seed": SEED,
        "plan": frozen_plan,
        "plan_sha256": canonical_sha256(plan(args.scope)),
        "host_preflight": host_preflight,
        "cell_count": len(validated_cells),
        "arm_count": len(validated_cells) * len(PROVIDERS),
        "all_providers_byte_exact": all_exact,
        "provider_classification": {
            provider: {
                "exact_cell_count": exact_counts[provider],
                "mismatch_cell_count": len(mismatches[provider]),
                "mismatches": mismatches[provider],
            }
            for provider in PROVIDERS
        },
        "all_outputs_finite_and_repeatable": True,
        "timing_classification": "descriptive_fixed_provider_order",
        "cells": validated_cells,
        "worker_sha256": WORKER_SHA256,
        "driver_sha256": script_sha256,
        "runtime_stage": str(STAGE),
        "runtime_manifest_sha256": STAGE_MANIFEST_SHA256,
        "driver_process_identity": {
            "pid": os.getpid(),
            "nonce_sha256": driver_nonce_sha256,
        },
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
    }
    if sha256(script) != script_sha256 or sha256(WORKER) != WORKER_SHA256:
        raise RuntimeError("driver/worker closure changed during the gate")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("authority evidence changed during the gate")
    atomic_write_json(summary_path, summary, summary_nonce)
    verify_host_and_storage()
    if not summary_path.is_file():
        raise RuntimeError("summary evidence disappeared after final write")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
