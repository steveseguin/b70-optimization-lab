#!/usr/bin/env python3
"""Direct-call cold-counter fixture for the separate Laguna gate+up M=8 path.

This intentionally does not start a subprocess or construct a model service.
The separately frozen counter runner owns profiler, source, idle, and physical
device preflight.  This fixture owns only the selected pair: thirteen
completion-bounded, cold-cache gate-then-up invocations on one visible XPU.

The control and candidate primitives are imported from the successful frozen
gate+up component runtime adapter.  They deliberately retain two projections:
there is no N=512 merge, B=16 packing, fusion, reordering, overlap, or
shared-down treatment in this fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

import gate_laguna_shared_gate_up_mm_component as contract
import gate_laguna_shared_gate_up_mm_stage0 as stage0
import run_laguna_shared_gate_up_mm_component as component_runtime
import run_laguna_shared_gate_up_mm_stage0 as stage0_runtime


ARTIFACT_ROOT_LITERAL = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
ARTIFACT_ROOT = ARTIFACT_ROOT_LITERAL.resolve()
NVME_MOUNT = Path("/mnt/fast-ai")
NVME_SOURCE, NVME_FSTYPE = "/dev/nvme0n1p2", "ext4"
FIXTURE_PATH = Path(__file__).resolve()
COMPONENT_RUNTIME_PATH = Path(component_runtime.__file__).resolve()
COMPONENT_CONTRACT_PATH = Path(contract.__file__).resolve()
STAGE0_RUNTIME_PATH = Path(stage0_runtime.__file__).resolve()

ROWS, HIDDEN, PROJECTION = 8, 3072, 256
EPOCH = 30_000
PAIRS = 13
PROJECTIONS_PER_PAIR = 2
SELECTED_GEMM_CALLS = PAIRS * PROJECTIONS_PER_PAIR
EVICTION_BYTES = 128 * 1024 * 1024
EVICTION_ELEMENTS = EVICTION_BYTES // 4
EXPECTED_TORCH_VERSION = "2.12.0+xpu"
EXPECTED_PYTHON_SHA256 = (
    "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_argument(value: str) -> str:
    value = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA-256")
    return value


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _mount_field(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def mount_identity() -> dict[str, str]:
    candidates: list[tuple[int, str, str, str]] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, separator, after = line.partition(" - ")
        require(bool(separator), "malformed mountinfo row")
        left, right = before.split(), after.split()
        require(len(left) >= 6 and len(right) >= 2, "short mountinfo row")
        point = _mount_field(left[4])
        try:
            NVME_MOUNT.relative_to(Path(point))
        except ValueError:
            continue
        candidates.append((len(point), point, right[0], _mount_field(right[1])))
    require(bool(candidates), "no mount record for /mnt/fast-ai")
    _length, point, filesystem, source = max(candidates)
    require(
        source == NVME_SOURCE and filesystem == NVME_FSTYPE,
        "Laguna evidence is not on the frozen local NVMe/ext4 mount",
    )
    require(
        os.stat(ARTIFACT_ROOT).st_dev == os.stat(NVME_MOUNT).st_dev,
        "artifact root device differs from /mnt/fast-ai",
    )
    return {
        "target": str(NVME_MOUNT),
        "mount_point": point,
        "source": source,
        "filesystem": filesystem,
    }


def require_output_path(path: Path) -> Path:
    require(
        ARTIFACT_ROOT == ARTIFACT_ROOT_LITERAL
        and not ARTIFACT_ROOT_LITERAL.is_symlink(),
        "artifact root is a symlink or resolved-path alias",
    )
    require(
        path.is_absolute() and path.suffix == ".json",
        "fixture output must be an absolute JSON path",
    )
    require(
        not path.exists() and not path.is_symlink(), "fixture output already exists"
    )
    parent = path.parent.resolve(strict=True)
    resolved = parent / path.name
    require(
        resolved == path
        and _within(resolved, ARTIFACT_ROOT)
        and not str(resolved).startswith(("/media/", "/mnt/usb-models/")),
        "fixture output escaped the local-NVMe artifact root",
    )
    mount_identity()
    return resolved


def exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
    )
    try:
        pending = memoryview(encoded)
        while pending:
            written = os.write(descriptor, pending)
            require(written > 0, "short fixture evidence write")
            pending = pending[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _raw_hash(tensor: Any, label: str, shape: tuple[int, ...]) -> str:
    return stage0_runtime._record_tensor(tensor, label, shape)["raw_bf16_le_sha256"]


def _require_pair_environment(rank: int, output: Path) -> dict[str, str]:
    # The counter runner must give this direct-call child the same frozen eager
    # pair selector surface as the passed component runtime path.
    expected = contract.environment(str(output.parent), rank)
    observed = {name: os.environ.get(name) for name in expected}
    require(
        observed == expected,
        "gate+up counter environment differs from frozen component contract",
    )
    require(
        observed["VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM"] == "1"
        and observed["VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM"] == "0"
        and observed["VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM"] == "0",
        "gate+up selector exclusivity drift",
    )
    return observed


def direct_runtime_identity(rank: int, output: Path) -> dict[str, Any]:
    require(rank in contract.CARDS, "invalid physical rank")
    require(
        sha256_file(Path(sys.executable)) == EXPECTED_PYTHON_SHA256,
        "Python interpreter SHA drift",
    )
    require(torch.__version__ == EXPECTED_TORCH_VERSION, "Torch version drift")
    require(
        Path(torch.__file__).resolve()
        == Path(
            stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY["files"]["torch_init"][
                "resolved_path"
            ]
        ),
        "Torch path drift",
    )
    for name, path in stage0_runtime.EXPECTED_BINARY_PATHS.items():
        require(
            path.is_file() and sha256_file(path) == stage0.EXPECTED_BINARY_SHA256[name],
            f"runtime binary SHA drift: {name}",
        )
    for name, record in stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY["files"].items():
        path = Path(record["path"])
        require(
            path.is_file() and sha256_file(path) == record["sha256"],
            f"runtime file SHA drift: {name}",
        )
    require(
        sha256_file(stage0_runtime.MODEL_CONFIG) == stage0.EXPECTED_MODEL_CONFIG_SHA256,
        "model config SHA drift",
    )
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    taint = Path("/proc/sys/kernel/tainted").read_text().strip()
    require(
        boot_id == stage0.EXPECTED_BOOT_ID and taint == "0",
        "boot or kernel-taint drift",
    )
    environment = _require_pair_environment(rank, output)
    require(torch.xpu.device_count() == 1, "fixture requires exactly one visible XPU")
    torch.xpu.set_device(0)
    require(
        torch.xpu.get_device_name(0) == stage0.EXPECTED_DEVICE_NAME,
        "visible XPU name drift",
    )
    return {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "argv": list(sys.argv),
        "fixture": {"path": str(FIXTURE_PATH), "sha256": sha256_file(FIXTURE_PATH)},
        "component_contract": {
            "path": str(COMPONENT_CONTRACT_PATH),
            "sha256": sha256_file(COMPONENT_CONTRACT_PATH),
        },
        "component_runtime": {
            "path": str(COMPONENT_RUNTIME_PATH),
            "sha256": sha256_file(COMPONENT_RUNTIME_PATH),
        },
        "stage0_runtime": {
            "path": str(STAGE0_RUNTIME_PATH),
            "sha256": sha256_file(STAGE0_RUNTIME_PATH),
        },
        "model_config": {
            "path": str(stage0_runtime.MODEL_CONFIG),
            "sha256": stage0.EXPECTED_MODEL_CONFIG_SHA256,
        },
        "environment": environment,
        "boot_id": boot_id,
        "kernel_taint": taint,
        "visible_torch_xpu_count": 1,
        "visible_torch_xpu_name": stage0.EXPECTED_DEVICE_NAME,
        "expected_physical_device": contract.CARDS[rank],
        "mount": mount_identity(),
        "subprocesses_started": 0,
    }


def _bf16(shape: tuple[int, ...], seed: int, torch_module: Any) -> Any:
    generator = torch_module.Generator(device="cpu")
    generator.manual_seed(seed)
    return (
        torch_module.randn(shape, generator=generator, dtype=torch_module.float32)
        .mul_(0.5)
        .to(torch_module.bfloat16)
        .contiguous()
    )


def make_rank_invariant_fixture(torch_module: Any) -> tuple[Any, Any, Any]:
    rows = _bf16((ROWS, HIDDEN), EPOCH * 10, torch_module).to("xpu")
    gate_weight = _bf16((PROJECTION, HIDDEN), EPOCH * 10 + 1, torch_module).to("xpu")
    up_weight = _bf16((PROJECTION, HIDDEN), EPOCH * 10 + 2, torch_module).to("xpu")
    require(
        all(
            t.dtype == torch_module.bfloat16 and t.is_contiguous()
            for t in (rows, gate_weight, up_weight)
        )
        and tuple(rows.shape) == (ROWS, HIDDEN)
        and tuple(gate_weight.shape) == tuple(up_weight.shape) == (PROJECTION, HIDDEN),
        "pair fixture BF16 geometry/layout drift",
    )
    return rows, gate_weight, up_weight


def _control_pair(
    rows: Any, gate_weight: Any, up_weight: Any, torch_module: Any
) -> tuple[Any, Any]:
    rows_bmm = rows.unsqueeze(1)
    gate_expanded = gate_weight.t().unsqueeze(0).expand(ROWS, -1, -1)
    up_expanded = up_weight.t().unsqueeze(0).expand(ROWS, -1, -1)
    # Existing component helpers are the frozen literal BMM control path.
    gate = component_runtime._control(
        rows_bmm,
        gate_expanded,
        torch_module.empty(
            (ROWS, 1, PROJECTION), dtype=torch_module.bfloat16, device="xpu"
        ),
        torch_module,
    )
    up = component_runtime._control(
        rows_bmm,
        up_expanded,
        torch_module.empty(
            (ROWS, 1, PROJECTION), dtype=torch_module.bfloat16, device="xpu"
        ),
        torch_module,
    )
    return gate.squeeze(1), up.squeeze(1)


def _candidate_pair(
    rows: Any, gate_weight: Any, up_weight: Any, torch_module: Any
) -> tuple[Any, Any]:
    # Existing component helpers are the frozen two-native-MM candidate path.
    gate = component_runtime._candidate(
        rows,
        gate_weight.t(),
        torch_module.empty(
            (ROWS, PROJECTION), dtype=torch_module.bfloat16, device="xpu"
        ),
        torch_module,
    )
    up = component_runtime._candidate(
        rows,
        up_weight.t(),
        torch_module.empty(
            (ROWS, PROJECTION), dtype=torch_module.bfloat16, device="xpu"
        ),
        torch_module,
    )
    return gate, up


def _selected_pair(
    arm: str, rows: Any, gate_weight: Any, up_weight: Any, torch_module: Any
) -> tuple[Any, Any]:
    if arm == "control":
        return _control_pair(rows, gate_weight, up_weight, torch_module)
    return _candidate_pair(rows, gate_weight, up_weight, torch_module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", choices=range(4), type=int, required=True)
    parser.add_argument("--arm", choices=("control", "candidate"), required=True)
    parser.add_argument(
        "--expected-fixture-sha256", type=sha256_argument, required=True
    )
    parser.add_argument("--authorization-sha256", type=sha256_argument, required=True)
    parser.add_argument("--protocol-sha256", type=sha256_argument, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    require(
        sha256_file(FIXTURE_PATH) == args.expected_fixture_sha256,
        "fixture source SHA mismatch",
    )
    output = require_output_path(args.out)
    identity = direct_runtime_identity(args.rank, output)
    rows, gate_weight, up_weight = make_rank_invariant_fixture(torch)
    torch.xpu.synchronize()
    inputs = {
        "rows": _raw_hash(rows, "counter.rows", (ROWS, HIDDEN)),
        "gate_weight": _raw_hash(
            gate_weight, "counter.gate_weight", (PROJECTION, HIDDEN)
        ),
        "up_weight": _raw_hash(up_weight, "counter.up_weight", (PROJECTION, HIDDEN)),
    }
    inputs["combined"] = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    eviction = torch.zeros(EVICTION_ELEMENTS, dtype=torch.float32, device="xpu")
    pair_hashes: list[dict[str, str]] = []
    boundary_hashes: dict[str, str] | None = None
    with torch.no_grad():
        for index in range(PAIRS):
            eviction.add_(1)
            torch.xpu.synchronize()  # completion boundary and eviction before the pair
            gate, up = _selected_pair(args.arm, rows, gate_weight, up_weight, torch)
            torch.xpu.synchronize()  # one completion boundary after ordered gate then up
            entry = {
                "pair": str(index),
                "gate": _raw_hash(
                    gate, f"counter.pair.{index}.gate", (ROWS, PROJECTION)
                ),
                "up": _raw_hash(up, f"counter.pair.{index}.up", (ROWS, PROJECTION)),
            }
            observed = {"gate": entry["gate"], "up": entry["up"]}
            if boundary_hashes is None:
                boundary_hashes = observed
            require(
                observed == boundary_hashes, "selected pair raw BF16 boundary drift"
            )
            pair_hashes.append(entry)
    require(
        len(pair_hashes) == PAIRS
        and boundary_hashes is not None
        and len({(row["gate"], row["up"]) for row in pair_hashes}) == 1,
        "selected pair output is nondeterministic",
    )

    payload: dict[str, Any] = {
        "format": "laguna-shared-gate-up-mm-cold-counter-fixture-v2",
        "status": "fixture-complete",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "authorization_sha256": args.authorization_sha256,
        "protocol_sha256": args.protocol_sha256,
        "fixture_source_sha256": args.expected_fixture_sha256,
        "identity": identity,
        "rank": args.rank,
        "arm": args.arm,
        "epoch": EPOCH,
        "geometry": {
            "rows": ROWS,
            "k": HIDDEN,
            "n": PROJECTION,
            "dtype": "torch.bfloat16",
            "rows_contiguous": True,
            "gate_weight_contiguous": True,
            "up_weight_contiguous": True,
        },
        "pair_order": ["gate_proj", "up_proj"],
        "pairs": PAIRS,
        "selected_pair_invocations": PAIRS,
        "selected_gemm_calls": SELECTED_GEMM_CALLS,
        "control_primitives_per_pair": ["torch.bmm", "torch.bmm"],
        "candidate_primitives_per_pair": ["torch.mm", "torch.mm"],
        "completion_boundary_before_each_pair": True,
        "completion_boundary_after_each_pair": True,
        "eviction_bytes_before_each_pair": EVICTION_BYTES,
        "input_sha256": inputs,
        "input_fixture_sha256": inputs["combined"],
        "boundary_sha256": boundary_hashes,
        "all_pair_output_sha256": pair_hashes,
        "counter_execution_performed": True,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "submission_performed": False,
    }
    exclusive_json(output, payload)
    print(
        json.dumps(
            {"status": payload["status"], "out": str(output), "pid": os.getpid()},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
