#!/usr/bin/env python3
"""Run and verify a fresh-process control/candidate/control HC bracket."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys


PAIR_LOCK_PATH = Path("/tmp/q38-hc-m1-grouped-gemm-pair.lock")
EXPECTED_SYCL = Path("/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8")
LOADER_SUFFIX = (
    "/home/steve/.venvs/vllm-xpu/lib",
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
    "/opt/intel/oneapi/compiler/2025.3/lib",
    "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive(path: Path, contents: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(contents)


def read_manifest(stage: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (stage / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        entries[name.removeprefix("*")] = digest
    return entries


def verify_loader_closure(
    stage: Path, environment: dict[str, str], manifest: dict[str, str]
) -> tuple[str, dict[str, str]]:
    extension = stage / "_xpu_C.abi3.so"
    completed = subprocess.run(
        ["ldd", str(extension)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    closure = completed.stdout
    if "not found" in closure:
        raise RuntimeError(f"runtime-stage loader dependency missing:\n{closure}")
    for name in manifest:
        if name == "_xpu_C.abi3.so" or not name.endswith(".so"):
            continue
        expected = f"{name} => {stage}/{name}"
        if expected not in closure:
            raise RuntimeError(
                f"custom library {name} did not resolve in stage:\n{closure}"
            )
    sycl_match = re.search(r"libsycl\.so\.8 => (\S+)", closure)
    if sycl_match is None or "libsycl.so.9" in closure:
        raise RuntimeError(f"runtime stage is not exclusively SYCL 8:\n{closure}")
    presented_sycl = Path(sycl_match.group(1))
    resolved_sycl = presented_sycl.resolve()
    if resolved_sycl != EXPECTED_SYCL.resolve():
        raise RuntimeError(f"unexpected SYCL 8 provider: {presented_sycl}")
    return closure, {
        "loader_path": str(presented_sycl),
        "path": str(resolved_sycl),
        "sha256": sha256(resolved_sycl),
    }


def verify_runpaths(stage: Path, manifest: dict[str, str]) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    for name in sorted(manifest):
        if not name.endswith(".so"):
            continue
        completed = subprocess.run(
            ["readelf", "-d", str(stage / name)],
            check=True,
            capture_output=True,
            text=True,
        )
        relevant = [
            line.strip()
            for line in completed.stdout.splitlines()
            if "NEEDED" in line or "RPATH" in line or "RUNPATH" in line
        ]
        runpaths = [line for line in relevant if "RUNPATH" in line]
        if len(runpaths) != 1 or "Library runpath: [$ORIGIN]" not in runpaths[0]:
            raise RuntimeError(f"{name} does not have exact $ORIGIN RUNPATH")
        if any(
            forbidden in line
            for line in relevant
            for forbidden in ("/home/steve/src", "/mnt/usb-models/qwen38-build/xpu-hc")
        ):
            raise RuntimeError(f"{name} embeds a build/source path")
        evidence[name] = relevant
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-stage", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--layer", type=int, choices=(0, 47), required=True)
    parser.add_argument("--projection", choices=("down", "up"), required=True)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    benchmark = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")
    driver = Path(__file__)
    benchmark_sha256 = sha256(benchmark)
    driver_sha256 = sha256(driver)
    stage = args.runtime_stage.resolve()
    pair_lock = PAIR_LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(pair_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise RuntimeError(f"component pair lock is held: {PAIR_LOCK_PATH}") from error
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    arm_paths = {
        label: output.with_name(f"{output.stem}-{label}.json")
        for label in ("control_before", "candidate", "control_after")
    }
    stderr_paths = {
        label: output.with_name(f"{output.stem}-{label}.stderr.txt")
        for label in arm_paths
    }
    stdout_paths = {
        label: output.with_name(f"{output.stem}-{label}.stdout.txt")
        for label in arm_paths
    }
    reserved_paths = (
        output,
        *arm_paths.values(),
        *stderr_paths.values(),
        *stdout_paths.values(),
    )
    existing = [str(path) for path in reserved_paths if path.exists()]
    if existing:
        raise RuntimeError(f"refusing to overwrite evidence: {existing}")
    environment = os.environ.copy()
    environment["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    environment["LD_LIBRARY_PATH"] = ":".join((str(stage), *LOADER_SUFFIX))
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest_path = stage / "SHA256SUMS"
    manifest_sha256 = sha256(manifest_path)
    runtime_manifest = read_manifest(stage)
    runpath_evidence = verify_runpaths(stage, runtime_manifest)
    loader_closure, sycl_identity = verify_loader_closure(
        stage, environment, runtime_manifest
    )

    arms: list[dict[str, object]] = []
    for label, provider in (
        ("control_before", "linear"),
        ("candidate", "grouped"),
        ("control_after", "linear"),
    ):
        if sha256(benchmark) != benchmark_sha256:
            raise RuntimeError("benchmark changed before an arm")
        if sha256(driver) != driver_sha256:
            raise RuntimeError("pair driver changed before an arm")
        if sha256(manifest_path) != manifest_sha256:
            raise RuntimeError("runtime manifest changed before an arm")
        command = [
            sys.executable,
            str(benchmark),
            "--runtime-stage",
            str(stage),
            "--model",
            str(args.model.resolve()),
            "--model-revision",
            args.model_revision,
            "--layer",
            str(args.layer),
            "--projection",
            args.projection,
            "--provider",
            provider,
            "--seed",
            str(args.seed),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        write_exclusive(stdout_paths[label], completed.stdout)
        write_exclusive(stderr_paths[label], completed.stderr)
        if completed.returncode != 0:
            raise RuntimeError(
                f"{label} arm failed with rc={completed.returncode}; "
                f"see {stderr_paths[label]}"
            )
        try:
            arm = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"{label} returned invalid JSON; see {stdout_paths[label]}"
            ) from error
        if arm.get("schema_version") != 1 or arm.get("status") != "component_arm_valid":
            raise RuntimeError(f"{label} returned an invalid arm status")
        if arm.get("provider") != provider:
            raise RuntimeError(f"{label} provider identity mismatch")
        if arm.get("layer") != args.layer or arm.get("projection") != args.projection:
            raise RuntimeError(f"{label} shape-selection identity mismatch")
        if arm.get("seed") != args.seed:
            raise RuntimeError(f"{label} seed identity mismatch")
        expected_repeats = {
            "warmups": 100,
            "timed_batches": 21,
            "iterations_per_batch": 100,
            "hash": 100,
        }
        if arm.get("repeats") != expected_repeats:
            raise RuntimeError(f"{label} repeat contract mismatch")
        if sha256(benchmark) != benchmark_sha256:
            raise RuntimeError("benchmark changed during an arm")
        if sha256(driver) != driver_sha256:
            raise RuntimeError("pair driver changed during an arm")
        if sha256(manifest_path) != manifest_sha256:
            raise RuntimeError("runtime manifest changed during an arm")
        arm["bracket_label"] = label
        write_exclusive(
            arm_paths[label], json.dumps(arm, indent=2, sort_keys=True) + "\n"
        )
        arms.append(arm)

    identity_fields = (
        "input_sha256",
        "weight_sha256",
        "model_revision",
        "model_index_sha256",
        "model_config_sha256",
        "model_shard",
        "model_shard_sha256",
        "model",
        "runtime_stage",
        "runtime_manifest",
        "runtime_manifest_sha256",
        "loader_environment",
        "library",
        "library_sha256",
        "device",
        "layer",
        "projection",
        "shape",
        "seed",
        "input_dtype",
        "weight_dtype",
        "weight_names",
        "weight_layout_nk",
        "packed_layout_ekn",
        "consumed_width",
        "repeats",
    )
    for field in identity_fields:
        if len({json.dumps(arm[field], sort_keys=True) for arm in arms}) != 1:
            raise RuntimeError(f"bracket identity mismatch: {field}")
    output_hashes = {str(arm["consumed_output_sha256"]) for arm in arms}
    exact = len(output_hashes) == 1
    controls = [
        float(arms[index]["timing_us"]["median"])  # type: ignore[index]
        for index in (0, 2)
    ]
    candidate = float(arms[1]["timing_us"]["median"])  # type: ignore[index]
    control_median = statistics.median(controls)
    if any(
        not math.isfinite(value) or value <= 0.0 for value in (*controls, candidate)
    ):
        raise RuntimeError("pair contains a non-finite or non-positive timing")
    latency_reduction_percent = (1.0 - candidate / control_median) * 100.0
    control_drift_percent = abs(controls[1] / controls[0] - 1.0) * 100.0
    result = {
        "schema_version": 1,
        "status": "pair_passed" if exact else "pair_rejected_output_mismatch",
        "classification": "hot_weight_component_screen_only",
        "benchmark_sha256": benchmark_sha256,
        "driver_sha256": driver_sha256,
        "loader_closure": loader_closure.splitlines(),
        "runpath_evidence": runpath_evidence,
        "sycl_identity": sycl_identity,
        "layer": args.layer,
        "projection": args.projection,
        "seed": args.seed,
        "exact_consumed_output": exact,
        "consumed_output_sha256_values": sorted(output_hashes),
        "control_median_us": control_median,
        "candidate_median_us": candidate,
        "latency_reduction_percent": latency_reduction_percent,
        "control_drift_percent": control_drift_percent,
        "control_drift_limit_percent": 3.0,
        "eligible_for_round_robin_followup": (
            exact and latency_reduction_percent >= 5.0 and control_drift_percent <= 3.0
        ),
        "endpoint_claim_authorized": False,
        "arms": arms,
    }
    if sha256(benchmark) != benchmark_sha256 or sha256(driver) != driver_sha256:
        raise RuntimeError("tool identity changed before final evidence write")
    if sha256(manifest_path) != manifest_sha256:
        raise RuntimeError("runtime manifest changed before final evidence write")
    write_exclusive(output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not exact:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
