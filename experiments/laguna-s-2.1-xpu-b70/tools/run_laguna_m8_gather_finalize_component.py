#!/usr/bin/env python3
"""Fail-closed one-card evidence leg for Laguna M=8 gather/finalize.

Only the standard library is imported at module import time.  In particular,
torch and the three native modules are imported only after a canonical,
O_EXCL+fsync pre-import marker has sealed the card root and its runtime
directories.  The runner is deliberately a component harness, not a launch,
counter, profiler, W2, model, or endpoint proof.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import stat
import statistics
import sys
import uuid
from pathlib import Path
from typing import Any


RUNNER = Path(__file__).resolve()
RESULT = "component-result.json"
PREIMPORT = "runtime-preimport-seal.json"
STARTED = "tensor-work-started-checkpoint.json"
RUNTIME_BINDING = "runtime-card-binding-checkpoint.json"
TIMING = "timing.json"
PRE_EPOCHS = "pre-epochs"
POST_EPOCHS = "post-epochs"

TOKENS = 8
TOPK = 10
HIDDEN = 3072
RANKS = 4
LAYERS = 47
WARM_CYCLES = 20
ABBA_BLOCKS = 31
CYCLES_PER_ARM = 64
FINITE_BF16_COUNT = 65280


class ProvenExactnessFailure(RuntimeError):
    """A durable raw-BF16 mismatch or input mutation was observed."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_path(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regular_resolved(path: Path, label: str) -> Path:
    require(
        path.is_absolute() and path.is_file() and not path.is_symlink(),
        f"unsafe {label}",
    )
    resolved = path.resolve(strict=True)
    require(
        resolved.is_file() and not resolved.is_symlink(), f"unsafe resolved {label}"
    )
    return resolved


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        wrote = os.write(fd, data[offset:])
        require(wrote > 0, "short checkpoint write")
        offset += wrote


def write_canonical(path: Path, value: dict[str, Any]) -> None:
    require(
        path.parent.is_dir() and not path.parent.is_symlink(),
        "unsafe checkpoint parent",
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, canonical(value) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _open_directory(path: Path) -> int:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISDIR(os.fstat(fd).st_mode), "not a directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _mkdir_at(parent_fd: int, name: str) -> int:
    require(name not in {"", ".", ".."} and "/" not in name, "unsafe directory name")
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    os.chmod(name, 0o700, dir_fd=parent_fd, follow_symlinks=False)
    child = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
    )
    try:
        require(
            stat.S_ISDIR(os.fstat(child).st_mode),
            "created runtime path is not a directory",
        )
        return child
    except BaseException:
        os.close(child)
        raise


def seal_runtime_root(root: Path) -> list[str]:
    """Create every writable runtime directory before torch/native import."""
    require(
        root.is_absolute() and not root.exists() and not root.is_symlink(),
        "card root is not fresh",
    )
    require(
        root.parent.is_dir() and not root.parent.is_symlink(), "unsafe card-root parent"
    )
    parent_fd = _open_directory(root.parent)
    created: list[str] = []
    try:
        root_fd = _mkdir_at(parent_fd, root.name)
        created.append(".")
        try:
            cache_fd: int | None = None
            for name in ("home", "tmp", PRE_EPOCHS, POST_EPOCHS):
                child = _mkdir_at(root_fd, name)
                os.close(child)
                created.append(name)
            cache_fd = _mkdir_at(root_fd, "cache")
            created.append("cache")
            try:
                for name in ("pycache", "sycl", "torchinductor"):
                    child = _mkdir_at(cache_fd, name)
                    os.close(child)
                    created.append(f"cache/{name}")
            finally:
                os.close(cache_fd)
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return created


def _read_canonical_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    resolved = _regular_resolved(path, label)
    raw = resolved.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON") from error
    require(
        isinstance(value, dict) and raw == canonical(value) + b"\n",
        f"{label} is noncanonical",
    )
    return value, raw


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _validate_binary_manifest(
    packet: dict[str, Any],
) -> dict[str, dict[str, dict[str, str]]]:
    manifest = packet.get("binary_manifest")
    names = {
        "_C.abi3.so",
        "_xpu_C.abi3.so",
        "_moe_C.abi3.so",
        "libgrouped_gemm_xe_2.so",
    }
    require(
        isinstance(manifest, dict)
        and set(manifest) == {"installed", "candidate", "incumbent"},
        "binary manifest classes drift",
    )
    installed = manifest["installed"]
    require(
        isinstance(installed, dict) and set(installed) == names,
        "installed native manifest drift",
    )
    for role, entries in manifest.items():
        require(
            isinstance(entries, dict) and set(entries) == names,
            f"native filenames drift: {role}",
        )
        for filename, record in entries.items():
            require(
                isinstance(record, dict)
                and set(record) == {"path", "resolved_path", "sha256"},
                f"native record drift: {role}/{filename}",
            )
            path = _regular_resolved(Path(record["path"]), f"native {role}/{filename}")
            require(
                str(path) == record["resolved_path"]
                and sha_path(path) == record["sha256"]
                and _is_sha(record["sha256"]),
                f"native identity drift: {role}/{filename}",
            )
    return manifest


def _fixture_manifest(
    packet: dict[str, Any], fixture_arg: Path
) -> tuple[dict[str, Any], str]:
    fixture = packet.get("fixture")
    require(
        isinstance(fixture, dict) and set(fixture) == {"path", "sha256"},
        "fixture packet must bind one canonical manifest",
    )
    path = _regular_resolved(Path(fixture["path"]), "fixture manifest")
    require(
        fixture_arg == path
        and _is_sha(fixture["sha256"])
        and sha_path(path) == fixture["sha256"],
        "fixture manifest argv/hash drift",
    )
    manifest, raw = _read_canonical_json(path, "fixture manifest")
    require(sha_bytes(raw) == fixture["sha256"], "fixture manifest raw hash drift")
    return manifest, sha_bytes(raw)


def _validate_manifest_surface(manifest: dict[str, Any]) -> None:
    expected = {
        "format",
        "corpus_version",
        "random_full",
        "coverage",
        "downstream",
        "expected_cpu_input_hashes",
    }
    require(set(manifest) == expected, "fixture manifest schema drift")
    require(
        manifest["format"] == "laguna-m8-gather-finalize-fixture-manifest-v2",
        "fixture manifest format drift",
    )
    require(
        isinstance(manifest["corpus_version"], str) and manifest["corpus_version"],
        "missing corpus version",
    )
    random_full = manifest["random_full"]
    require(
        isinstance(random_full, dict) and set(random_full) == {"algorithm", "seeds"},
        "random corpus manifest drift",
    )
    seeds = random_full["seeds"]
    require(
        random_full["algorithm"] == "torch_cpu_generator_manual_seed_randn_v1"
        and isinstance(seeds, list)
        and 256 <= len(seeds) <= 512
        and all(isinstance(seed, int) and 0 <= seed < 2**63 for seed in seeds)
        and len(set(seeds)) == len(seeds),
        "random full corpus must provide 256+ distinct deterministic seeds",
    )
    coverage = manifest["coverage"]
    require(
        isinstance(coverage, dict)
        and set(coverage)
        == {
            "finite_bf16",
            "special_classes",
            "weight_edges",
            "tie_even",
            "route_patterns",
            "slot_rows",
        },
        "coverage manifest drift",
    )
    require(
        coverage["finite_bf16"]
        == {
            "excluded_exponent": 255,
            "count": FINITE_BF16_COUNT,
            "routed": True,
            "shared": True,
        },
        "finite BF16 coverage drift",
    )
    require(
        coverage["special_classes"]
        == ["positive_zero", "negative_zero", "subnormal", "infinity", "nan"],
        "special BF16 classification coverage drift",
    )
    require(
        coverage["weight_edges"]
        == [
            "positive_zero",
            "negative_zero",
            "positive_subnormal",
            "negative_subnormal",
            "near_one",
        ],
        "FP32 edge coverage drift",
    )
    require(
        coverage["tie_even"] is True
        and coverage["route_patterns"]
        == ["all_local", "all_remote", "mixed_remote_zero"]
        and coverage["slot_rows"] == {"slots": 10, "rows": 80},
        "fixture coverage declaration drift",
    )
    hashes = manifest["expected_cpu_input_hashes"]
    require(
        isinstance(hashes, dict) and hashes,
        "manifest must bind expected CPU input hashes",
    )
    downstream = manifest["downstream"]
    downstream_keys = {"format", "seed", "epsilon", "expected_cpu_static_input_hashes"}
    require(
        isinstance(downstream, dict) and set(downstream) == downstream_keys,
        "downstream manifest drift",
    )
    require(
        downstream["format"] == "laguna-m8-post-moe-fused-add-rmsnorm-v1"
        and isinstance(downstream["seed"], int),
        "production RMSNorm manifest identity drift",
    )
    require(
        isinstance(downstream["epsilon"], (int, float))
        and math.isfinite(float(downstream["epsilon"]))
        and float(downstream["epsilon"]) > 0.0,
        "unsafe model RMSNorm epsilon",
    )
    require(
        isinstance(downstream["expected_cpu_static_input_hashes"], dict)
        and downstream["expected_cpu_static_input_hashes"],
        "RMSNorm static hashes absent",
    )


def _validate_packet(
    packet: dict[str, Any], authorization: Path, fixture_arg: Path, rank: int
) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    require(packet.get("packet_path") == str(authorization), "authorization path drift")
    require(rank in range(RANKS), "rank must be 0..3")
    cards = packet.get("cards")
    require(
        isinstance(cards, list)
        and len(cards) == RANKS
        and [card.get("rank") for card in cards] == list(range(RANKS)),
        "packet cards drift",
    )
    card = cards[rank]
    physical = card.get("physical")
    require(
        isinstance(physical, dict)
        and set(physical) >= {"uuid", "pci_bdf_address", "drm_device"},
        "physical card binding absent",
    )
    require(
        isinstance(card.get("output_root"), str)
        and Path(card["output_root"]).is_absolute(),
        "unsafe output root",
    )
    protocol = packet.get("protocol")
    require(isinstance(protocol, dict), "protocol absent")
    require(
        protocol.get("tokens") == TOKENS
        and protocol.get("topk") == TOPK
        and protocol.get("hidden_size") == HIDDEN
        and protocol.get("local_experts") == 64
        and protocol.get("warm_cycles_per_arm") == WARM_CYCLES
        and protocol.get("abba_blocks") == ABBA_BLOCKS
        and protocol.get("cycles_per_arm_per_block") == CYCLES_PER_ARM
        and protocol.get("arm_order") == "A-B-B-A",
        "packet protocol drift",
    )
    selectors = packet.get("selectors")
    require(
        isinstance(selectors, dict)
        and selectors.get("VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE") == "1",
        "candidate selector is not packet-bound",
    )
    integration_ids = packet.get("integration_evidence_ids")
    require(
        isinstance(integration_ids, list)
        and integration_ids
        and all(isinstance(item, str) and item for item in integration_ids)
        and len(set(integration_ids)) == len(integration_ids),
        "packet-bound integration evidence IDs required",
    )
    binaries = _validate_binary_manifest(packet)
    manifest, manifest_sha = _fixture_manifest(packet, fixture_arg)
    _validate_manifest_surface(manifest)
    return card, manifest, manifest_sha, binaries


def _validate_runner_invocation(card: dict[str, Any]) -> dict[str, Any]:
    require(
        sys.argv == card["runner_argv"][1:],
        "runner argv drift from authorization",
    )
    require(
        dict(os.environ) == card["environment"],
        "runner environment drift from authorization",
    )
    runtime_root = Path(card["runtime_root"])
    require(
        runtime_root.is_absolute()
        and runtime_root.is_dir()
        and not runtime_root.is_symlink(),
        "precreated runtime root is unsafe",
    )
    path_keys = (
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "VLLM_CACHE_ROOT",
        "TRITON_CACHE_DIR",
        "NUMBA_CACHE_DIR",
        "PYTHONPYCACHEPREFIX",
        "SYCL_CACHE_DIR",
        "TORCHINDUCTOR_CACHE_DIR",
    )
    observed: dict[str, str] = {}
    for key in path_keys:
        path = Path(card["environment"][key])
        require(
            path.is_absolute()
            and path.is_relative_to(runtime_root)
            and path.is_dir()
            and not path.is_symlink(),
            f"unsafe or absent runtime directory: {key}",
        )
        observed[key] = str(path)
    return {"runtime_root": str(runtime_root), "environment_paths": observed}


def _sysfs_binding(physical: dict[str, Any]) -> dict[str, str]:
    drm = Path(physical["drm_device"])
    require(drm.name.startswith("card"), "packet DRM device is invalid")
    device = (Path("/sys/class/drm") / drm.name / "device").resolve(strict=True)
    require(
        device.is_dir() and str(device).startswith("/sys/devices/"),
        "unsafe DRM sysfs target",
    )
    vendor = (device / "vendor").read_text().strip()
    product = (device / "device").read_text().strip()
    require(
        device.name == physical["pci_bdf_address"]
        and vendor == "0x8086"
        and product == "0xe223",
        "packet BDF is not the expected B70",
    )
    return {
        "drm_device": str(drm),
        "pci_bdf_address": device.name,
        "vendor": vendor,
        "device": product,
        "sysfs_device": str(device),
    }


def _native_imports(
    torch: Any, binaries: dict[str, dict[str, dict[str, str]]]
) -> dict[str, dict[str, str]]:
    """Import every producer of the required ops and pin its loaded origin."""
    wanted = {
        "vllm_xpu_kernels._C": "_C.abi3.so",
        "vllm_xpu_kernels._xpu_C": "_xpu_C.abi3.so",
        "vllm_xpu_kernels._moe_C": "_moe_C.abi3.so",
    }
    observed: dict[str, dict[str, str]] = {}
    for name, filename in wanted.items():
        module = importlib.import_module(name)
        origin = getattr(module, "__file__", None)
        require(isinstance(origin, str), f"native module lacks origin: {name}")
        path = _regular_resolved(Path(origin), f"loaded native module {name}")
        record = binaries["installed"][filename]
        require(
            str(path) == record["resolved_path"] and sha_path(path) == record["sha256"],
            f"loaded native origin/hash drift: {name}",
        )
        observed[name] = {"path": str(path), "sha256": record["sha256"]}
    require(
        hasattr(torch.ops._moe_C, "moe_gather")
        and hasattr(torch.ops._moe_C, "laguna_m8_moe_gather_finalize")
        and hasattr(torch.ops._moe_C, "laguna_m8_moe_gather_finalize_diagnostic"),
        "required _moe_C symbols absent",
    )
    require(
        hasattr(torch.ops._C, "laguna_m8_scale_add"),
        "required incumbent _C scale/add symbol absent",
    )
    require(
        hasattr(torch.ops._xpu_C, "rank_order_bf16_sum")
        and hasattr(torch.ops._C, "fused_add_rms_norm"),
        "required production rank-sum/RMSNorm symbols absent",
    )
    return observed


def _runtime_uuid_binding(
    torch: Any, physical: dict[str, Any], sysfs: dict[str, str]
) -> dict[str, str]:
    require(
        torch.xpu.device_count() == 1 and torch.xpu.current_device() == 0,
        "exactly one re-indexed XPU is required",
    )
    properties = torch.xpu.get_device_properties(0)
    value = properties.uuid
    try:
        if isinstance(value, str):
            torch_uuid = uuid.UUID(value)
            raw = torch_uuid.bytes
        elif (
            type(value).__module__ == "torch._C" and type(value).__name__ == "_XPUuuid"
        ):
            octets = value.bytes
            require(
                isinstance(octets, list)
                and len(octets) == 16
                and all(isinstance(item, int) and 0 <= item <= 255 for item in octets),
                "Torch UUID byte view is malformed",
            )
            raw = bytes(octets)
            torch_uuid = uuid.UUID(bytes=raw)
            require(
                str(value).lower() == str(torch_uuid).lower(),
                "Torch UUID text/byte disagreement",
            )
        elif isinstance(value, (bytes, bytearray, memoryview)):
            raw = bytes(value)
            require(len(raw) == 16, "Torch UUID byte length drift")
            torch_uuid = uuid.UUID(bytes=raw)
        else:
            raise TypeError("unsupported Torch XPU UUID type")
    except (TypeError, ValueError, AttributeError) as error:
        raise RuntimeError("Torch XPU UUID is malformed") from error
    reversed_uuid = str(uuid.UUID(bytes=raw[::-1])).lower()
    require(
        reversed_uuid == physical["uuid"].lower()
        and sysfs["pci_bdf_address"] == physical["pci_bdf_address"],
        "reverse-byte Torch UUID does not bind to packet BDF",
    )
    return {
        "torch_runtime_uuid": str(torch_uuid).lower(),
        "torch_runtime_uuid_bytes_hex": raw.hex(),
        "runtime_uuid": reversed_uuid,
        "runtime_uuid_bytes_hex": raw[::-1].hex(),
        "runtime_uuid_mapping": "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes",
        "pci_bdf_address": sysfs["pci_bdf_address"],
    }


def _raw(tensor: Any, torch: Any) -> bytes:
    return tensor.detach().contiguous().to("cpu").view(torch.uint8).numpy().tobytes()


def _tensor_hash(tensor: Any, torch: Any) -> str:
    return sha_bytes(_raw(tensor, torch))


def _meta(tensor: Any) -> dict[str, Any]:
    return {
        "data_ptr": int(tensor.data_ptr()),
        "shape": list(tensor.shape),
        "stride": list(tensor.stride()),
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
        "numel": int(tensor.numel()),
        "element_size": int(tensor.element_size()),
    }


def _tensor_record(tensor: Any, torch: Any) -> dict[str, Any]:
    return {"metadata": _meta(tensor), "raw_le_sha256": _tensor_hash(tensor, torch)}


def _input_hashes(
    routes: Any, weights: Any, shared: Any, route_map: Any, torch: Any
) -> dict[str, str]:
    return {
        "routes_bf16_le_sha256": _tensor_hash(routes, torch),
        "weights_fp32_le_sha256": _tensor_hash(weights, torch),
        "shared_bf16_le_sha256": _tensor_hash(shared, torch),
        "route_map_uint32_le_sha256": _tensor_hash(route_map, torch),
    }


def _finite_bf16_bits(torch: Any) -> Any:
    values = torch.arange(65536, dtype=torch.int32, device="cpu")
    finite = values[(values & 0x7F80) != 0x7F80].to(torch.uint16)
    require(finite.numel() == FINITE_BF16_COUNT, "finite BF16 enumeration drift")
    return finite


def _corpus_specs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for index, seed in enumerate(manifest["random_full"]["seeds"]):
        specs.append(
            {
                "id": f"random-full-{index:03d}",
                "kind": "random_full",
                "seed": seed,
                "coverage": ["random_full"],
            }
        )
    width = TOKENS * HIDDEN
    chunks = math.ceil(FINITE_BF16_COUNT / width)
    for slot in range(TOPK):
        for chunk in range(chunks):
            specs.append(
                {
                    "id": f"routed-finite-slot-{slot}-chunk-{chunk}",
                    "kind": "routed_finite",
                    "slot": slot,
                    "chunk": chunk,
                    "coverage": ["finite_bf16_routed", f"slot_{slot}"],
                }
            )
    for chunk in range(chunks):
        specs.append(
            {
                "id": f"shared-finite-chunk-{chunk}",
                "kind": "shared_finite",
                "chunk": chunk,
                "coverage": ["finite_bf16_shared"],
            }
        )
    specs.extend(
        [
            {
                "id": "special-bf16-classification",
                "kind": "special_classification",
                "coverage": [
                    "positive_zero",
                    "negative_zero",
                    "subnormal",
                    "infinity",
                    "nan",
                ],
            },
            {
                "id": "fp32-weight-edges",
                "kind": "weight_edges",
                "coverage": ["fp32_zero", "fp32_subnormal", "fp32_near_one"],
            },
            {
                "id": "tie-even-midpoints",
                "kind": "tie_even",
                "coverage": ["tie_even_midpoints"],
            },
            {
                "id": "all-local",
                "kind": "route_pattern",
                "pattern": "all_local",
                "coverage": ["all_local"],
            },
            {
                "id": "all-remote",
                "kind": "route_pattern",
                "pattern": "all_remote",
                "coverage": ["all_remote"],
            },
            {
                "id": "mixed-remote-zero",
                "kind": "route_pattern",
                "pattern": "mixed_remote_zero",
                "coverage": ["mixed_remote_zero"],
            },
        ]
    )
    for slot in range(TOPK):
        specs.append(
            {
                "id": f"canonical-slot-{slot}",
                "kind": "canonical_slot",
                "slot": slot,
                "coverage": ["all_ten_slots", f"slot_{slot}", "all_80_rows"],
            }
        )
    require(
        sum(spec["kind"] == "random_full" for spec in specs) >= 256,
        "corpus lost random full fixtures",
    )
    return specs


def _validate_spec_coverage(specs: list[dict[str, Any]]) -> None:
    routed = {
        (spec.get("slot"), spec.get("chunk"))
        for spec in specs
        if spec["kind"] == "routed_finite"
    }
    shared = {spec.get("chunk") for spec in specs if spec["kind"] == "shared_finite"}
    chunks = math.ceil(FINITE_BF16_COUNT / (TOKENS * HIDDEN))
    require(
        routed == {(slot, chunk) for slot in range(TOPK) for chunk in range(chunks)}
        and shared == set(range(chunks)),
        "finite boundary corpus coverage drift",
    )
    require(
        {spec.get("slot") for spec in specs if spec["kind"] == "canonical_slot"}
        == set(range(TOPK)),
        "not all canonical slots are covered",
    )
    require(
        {spec.get("pattern") for spec in specs if spec["kind"] == "route_pattern"}
        == {"all_local", "all_remote", "mixed_remote_zero"},
        "route zero-pattern corpus drift",
    )


def _randn(shape: tuple[int, ...], seed: int, scale: float, torch: Any) -> Any:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    return (
        torch.randn(shape, generator=generator, dtype=torch.float32, device="cpu")
        * scale
    )


def _make_cpu_fixture(
    spec: dict[str, Any], finite_bits: Any, torch: Any
) -> dict[str, Any]:
    routes = torch.zeros((TOKENS * TOPK, HIDDEN), dtype=torch.bfloat16, device="cpu")
    weights = torch.zeros((TOKENS, TOPK), dtype=torch.float32, device="cpu")
    shared = torch.zeros((TOKENS, HIDDEN), dtype=torch.bfloat16, device="cpu")
    kind = spec["kind"]
    if kind == "random_full":
        seed = spec["seed"]
        routes.copy_(
            _randn((TOKENS * TOPK, HIDDEN), seed, 5.0, torch).to(torch.bfloat16)
        )
        weights.copy_(_randn((TOKENS, TOPK), seed ^ 0x6A47F00D, 1.0, torch))
        shared.copy_(
            _randn((TOKENS, HIDDEN), seed ^ 0x13579BDF, 3.0, torch).to(torch.bfloat16)
        )
    elif kind == "routed_finite":
        slot, chunk = spec["slot"], spec["chunk"]
        start, end = (
            chunk * TOKENS * HIDDEN,
            min((chunk + 1) * TOKENS * HIDDEN, FINITE_BF16_COUNT),
        )
        packed = torch.zeros(TOKENS * HIDDEN, dtype=torch.uint16)
        packed[: end - start].copy_(finite_bits[start:end])
        routes[slot::TOPK].copy_(packed.view(torch.bfloat16).view(TOKENS, HIDDEN))
        weights[:, slot].fill_(1.0)
    elif kind == "shared_finite":
        chunk = spec["chunk"]
        start, end = (
            chunk * TOKENS * HIDDEN,
            min((chunk + 1) * TOKENS * HIDDEN, FINITE_BF16_COUNT),
        )
        target = shared.view(torch.uint16).view(-1)
        target[: end - start].copy_(finite_bits[start:end])
    elif kind == "special_classification":
        special = torch.tensor(
            [
                0x0000,
                0x8000,
                0x0001,
                0x007F,
                0x8001,
                0x807F,
                0x7F80,
                0xFF80,
                0x7FC1,
                0x7FFF,
                0xFFC1,
                0xFFFF,
            ],
            dtype=torch.uint16,
        )
        routed_special = special.repeat(math.ceil((TOKENS * HIDDEN) / special.numel()))[
            : TOKENS * HIDDEN
        ]
        routes[0::TOPK].copy_(routed_special.view(torch.bfloat16).view(TOKENS, HIDDEN))
        reversed_special = special.to(torch.int32).flip(0).to(torch.uint16)
        shared.view(torch.uint16).view(-1).copy_(
            reversed_special.repeat(math.ceil((TOKENS * HIDDEN) / special.numel()))[
                : TOKENS * HIDDEN
            ]
        )
        weights[:, 0].fill_(1.0)
    elif kind == "weight_edges":
        routes.fill_(1.0)
        edge = torch.tensor(
            [
                0.0,
                -0.0,
                math.ldexp(1.0, -149),
                -math.ldexp(1.0, -149),
                0.99999994,
                1.00000012,
                1.0,
                -1.0,
            ],
            dtype=torch.float32,
        )
        weights.view(-1).copy_(
            edge.repeat(math.ceil((TOKENS * TOPK) / edge.numel()))[: TOKENS * TOPK]
        )
    elif kind == "tie_even":
        midpoint_weights = torch.tensor(
            [
                1.00390625,
                1.01171875,
                1.01953125,
                1.02734375,
                -1.00390625,
                -1.01171875,
                1.00390625,
                1.01171875,
            ],
            dtype=torch.float32,
        )
        routes[0::TOPK].fill_(1.0)
        weights[:, 0].copy_(midpoint_weights)
        shared.fill_(1.0)
    elif kind == "route_pattern":
        pattern = spec["pattern"]
        weights.fill_(1.0)
        if pattern == "all_local":
            routes[:, 0].fill_(1.0)
        elif pattern == "all_remote":
            pass
        elif pattern == "mixed_remote_zero":
            zero_rows = {0, 9, 10, 19, 23, 31, 40, 47, 58, 70, 79}
            for row in range(TOKENS * TOPK):
                if row not in zero_rows:
                    routes[row, 0] = 1.0
        else:
            raise RuntimeError("unknown route pattern")
    elif kind == "canonical_slot":
        slot = spec["slot"]
        routes[slot::TOPK].fill_(1.0)
        weights[:, slot].fill_(1.0)
    else:
        raise RuntimeError("unknown fixture kind")
    route_map = torch.arange(TOKENS * TOPK, dtype=torch.int32, device="cpu").view(
        TOKENS, TOPK
    )
    zero_rows = [
        row
        for row in range(TOKENS * TOPK)
        if not bool(torch.count_nonzero(routes[row]).item())
    ]
    if kind == "route_pattern":
        pattern = spec["pattern"]
        if pattern == "all_local":
            require(zero_rows == [], "all-local fixture contains a zero route row")
        elif pattern == "all_remote":
            require(
                zero_rows == list(range(TOKENS * TOPK)),
                "all-remote fixture is not all literal zero rows",
            )
        else:
            require(
                zero_rows == [0, 9, 10, 19, 23, 31, 40, 47, 58, 70, 79],
                "mixed fixture zero rows drift",
            )
    return {
        "spec": spec,
        "routes": routes,
        "weights": weights,
        "shared": shared,
        "route_map": route_map,
        "zero_rows": zero_rows,
    }


def _validate_cpu_fixture(
    item: dict[str, Any], expected: dict[str, Any], torch: Any
) -> dict[str, str]:
    actual = _input_hashes(
        item["routes"], item["weights"], item["shared"], item["route_map"], torch
    )
    spec = item["spec"]
    wanted = expected.get(spec["id"])
    require(
        isinstance(wanted, dict) and wanted == actual,
        f"manifest CPU input hashes drift: {spec['id']}",
    )
    return actual


def _to_xpu(
    cpu_item: dict[str, Any], input_hashes: dict[str, str], torch: Any
) -> dict[str, Any]:
    return {
        "spec": cpu_item["spec"],
        "routes": cpu_item["routes"].to("xpu"),
        "weights": cpu_item["weights"].to("xpu"),
        "shared": cpu_item["shared"].to("xpu"),
        "route_map": cpu_item["route_map"].to("xpu"),
        "cpu_input_hashes": input_hashes,
        "zero_rows": cpu_item["zero_rows"],
    }


def _literal_oracle(
    routes: Any, weights: Any, shared: Any, torch: Any
) -> tuple[Any, Any, Any]:
    """Independent ordered FP32/BF16 reference; it never calls a native op."""
    accum = torch.zeros((TOKENS, HIDDEN), dtype=torch.float32, device="cpu")
    for slot in range(TOPK):
        selected = routes[slot::TOPK].float()
        product = torch.mul(selected, weights[:, slot].unsqueeze(1))
        accum = torch.add(accum, product)
    routed = accum.to(torch.bfloat16)
    scaled = torch.mul(routed.float(), 2.5).to(torch.bfloat16)
    final = torch.add(shared.float(), scaled.float()).to(torch.bfloat16)
    return routed, scaled, final


def _classify_bf16(tensor: Any, torch: Any) -> dict[str, Any]:
    bits = tensor.detach().contiguous().to("cpu").view(torch.uint16).to(torch.int32)
    exponent = bits & 0x7F80
    fraction = bits & 0x007F
    sign = bits & 0x8000
    nan_mask = (exponent == 0x7F80) & (fraction != 0)
    nan_payloads = fraction[nan_mask].to(torch.uint8).numpy().tobytes()
    return {
        "positive_zero": int(
            ((exponent == 0) & (fraction == 0) & (sign == 0)).sum().item()
        ),
        "negative_zero": int(
            ((exponent == 0) & (fraction == 0) & (sign != 0)).sum().item()
        ),
        "subnormal": int(((exponent == 0) & (fraction != 0)).sum().item()),
        "negative_subnormal": int(
            ((exponent == 0) & (fraction != 0) & (sign != 0)).sum().item()
        ),
        "finite_normal": int(((exponent != 0) & (exponent != 0x7F80)).sum().item()),
        "infinity": int(((exponent == 0x7F80) & (fraction == 0)).sum().item()),
        "positive_infinity": int(
            ((exponent == 0x7F80) & (fraction == 0) & (sign == 0)).sum().item()
        ),
        "negative_infinity": int(
            ((exponent == 0x7F80) & (fraction == 0) & (sign != 0)).sum().item()
        ),
        "nan": int(nan_mask.sum().item()),
        "positive_nan": int((nan_mask & (sign == 0)).sum().item()),
        "negative_nan": int((nan_mask & (sign != 0)).sum().item()),
        "sign_bit_set": int((sign != 0).sum().item()),
        "nan_payloads_sha256": sha_bytes(nan_payloads),
    }


def _comparison(left: Any, right: Any, torch: Any) -> dict[str, Any]:
    left_cpu, right_cpu = (
        left.detach().contiguous().to("cpu"),
        right.detach().contiguous().to("cpu"),
    )
    left_class, right_class = (
        _classify_bf16(left_cpu, torch),
        _classify_bf16(right_cpu, torch),
    )
    raw_equal = _raw(left_cpu, torch) == _raw(right_cpu, torch)
    contains_nan = left_class["nan"] != 0 or right_class["nan"] != 0
    value: dict[str, Any] = {
        "left_raw_bf16_le_sha256": _tensor_hash(left_cpu, torch),
        "right_raw_bf16_le_sha256": _tensor_hash(right_cpu, torch),
        "raw_uint16_equal": raw_equal,
        "left_classification": left_class,
        "right_classification": right_class,
        "contains_nan": contains_nan,
    }
    if contains_nan:
        value.update(
            torch_equal=None,
            torch_equal_policy="inapplicable_when_nan_present_raw_bits_and_classification_required",
            classification_equal=left_class == right_class,
            passed=raw_equal and left_class == right_class,
        )
    else:
        equal = bool(torch.equal(left_cpu, right_cpu))
        value.update(
            torch_equal=equal,
            torch_equal_policy="required_for_finite_and_infinite_values",
            classification_equal=left_class == right_class,
            passed=raw_equal and equal and left_class == right_class,
        )
    return value


def _control(routed_out: Any, final_out: Any, item: dict[str, Any], torch: Any) -> None:
    torch.ops._moe_C.moe_gather(
        routed_out, item["routes"], item["weights"], item["route_map"], 64
    )
    torch.ops._C.laguna_m8_scale_add(final_out, item["shared"], routed_out)


def _candidate(final_out: Any, item: dict[str, Any], torch: Any) -> None:
    torch.ops._moe_C.laguna_m8_moe_gather_finalize(
        final_out, item["routes"], item["weights"], item["shared"], 64
    )


def _build_downstream_context(manifest: dict[str, Any], torch: Any) -> dict[str, Any]:
    cfg = manifest["downstream"]
    seed = cfg["seed"]

    def rnd_cpu(
        shape: tuple[int, ...], offset: int, dtype: Any, scale: float = 1.0
    ) -> Any:
        return _randn(shape, seed ^ offset, scale, torch).to(dtype)

    cpu_static = {
        "rank_tail": rnd_cpu((RANKS - 1, TOKENS, HIDDEN), 0x111, torch.bfloat16),
        "residual_base": rnd_cpu((TOKENS, HIDDEN), 0x222, torch.bfloat16),
        "norm_weight": (1.0 + rnd_cpu((HIDDEN,), 0x333, torch.float32, 0.01)).to(
            torch.bfloat16
        ),
    }
    static = {name: _tensor_hash(value, torch) for name, value in cpu_static.items()}
    require(
        static == cfg["expected_cpu_static_input_hashes"],
        "manifest RMSNorm static input hashes drift",
    )
    context = {name: value.to("xpu") for name, value in cpu_static.items()}
    for branch in ("control", "candidate"):
        rank_input = torch.empty(
            (RANKS, TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu"
        )
        rank_input[1:].copy_(context["rank_tail"])
        context[branch] = {
            "rank_input": rank_input,
            "hidden": torch.empty((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu"),
            "residual": torch.empty(
                (TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu"
            ),
        }
    context["epsilon"] = float(cfg["epsilon"])
    context["static_hashes"] = static
    return context


def _production_downstream(
    final: Any, context: dict[str, Any], branch: str, torch: Any
) -> dict[str, Any]:
    state = context[branch]
    state["rank_input"][0].copy_(final)
    rank_sum = torch.ops._xpu_C.rank_order_bf16_sum(state["rank_input"])
    # The production post-MoE boundary mutates independent cloned [8,3072]
    # hidden and residual tensors.  It is not a synthetic layer-norm replay.
    state["hidden"].copy_(rank_sum)
    state["residual"].copy_(context["residual_base"])
    torch.ops._C.fused_add_rms_norm(
        state["hidden"], state["residual"], context["norm_weight"], context["epsilon"]
    )
    return {
        "rank_order_bf16_sum": rank_sum,
        "fused_add_rms_norm_hidden": state["hidden"],
        "fused_add_rms_norm_residual": state["residual"],
    }


def _comparison_epoch(
    item: dict[str, Any], downstream_context: dict[str, Any], torch: Any
) -> dict[str, Any]:
    before = _input_hashes(
        item["routes"], item["weights"], item["shared"], item["route_map"], torch
    )
    require(
        before == item["cpu_input_hashes"],
        f"XPU input transfer hash drift: {item['spec']['id']}",
    )
    control_routed = torch.empty((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    control_final = torch.empty_like(control_routed)
    candidate_final = torch.empty_like(control_routed)
    candidate_repeat = torch.empty_like(control_routed)
    _control(control_routed, control_final, item, torch)
    _candidate(candidate_final, item, torch)
    _candidate(candidate_repeat, item, torch)
    diagnostic = torch.ops._moe_C.laguna_m8_moe_gather_finalize_diagnostic(
        item["routes"], item["weights"], item["shared"], 64
    )
    require(
        isinstance(diagnostic, (tuple, list)) and len(diagnostic) == 3,
        "candidate diagnostic ABI drift",
    )
    diagnostic_routed, diagnostic_scaled, diagnostic_final = diagnostic
    oracle_routed, oracle_scaled, oracle_final = _literal_oracle(
        item["routes"].to("cpu"),
        item["weights"].to("cpu"),
        item["shared"].to("cpu"),
        torch,
    )
    control_scaled_literal = torch.mul(control_routed.to("cpu").float(), 2.5).to(
        torch.bfloat16
    )
    control_downstream = _production_downstream(
        control_final, downstream_context, "control", torch
    )
    candidate_downstream = _production_downstream(
        candidate_final, downstream_context, "candidate", torch
    )
    pairs = {
        "control_routed_vs_literal_oracle": _comparison(
            control_routed, oracle_routed, torch
        ),
        "candidate_diagnostic_routed_vs_literal_oracle": _comparison(
            diagnostic_routed, oracle_routed, torch
        ),
        "candidate_diagnostic_routed_vs_control": _comparison(
            diagnostic_routed, control_routed, torch
        ),
        "candidate_diagnostic_scaled_vs_literal_oracle": _comparison(
            diagnostic_scaled, oracle_scaled, torch
        ),
        "control_scaled_literal_vs_literal_oracle": _comparison(
            control_scaled_literal, oracle_scaled, torch
        ),
        "candidate_diagnostic_scaled_vs_control_literal": _comparison(
            diagnostic_scaled, control_scaled_literal, torch
        ),
        "control_final_vs_literal_oracle": _comparison(
            control_final, oracle_final, torch
        ),
        "candidate_production_final_vs_literal_oracle": _comparison(
            candidate_final, oracle_final, torch
        ),
        "candidate_diagnostic_final_vs_literal_oracle": _comparison(
            diagnostic_final, oracle_final, torch
        ),
        "candidate_diagnostic_final_vs_control": _comparison(
            diagnostic_final, control_final, torch
        ),
        "control_final_vs_candidate_production": _comparison(
            control_final, candidate_final, torch
        ),
        "candidate_production_vs_diagnostic_final": _comparison(
            candidate_final, diagnostic_final, torch
        ),
        "candidate_repeat": _comparison(candidate_final, candidate_repeat, torch),
    }
    for name in (
        "rank_order_bf16_sum",
        "fused_add_rms_norm_hidden",
        "fused_add_rms_norm_residual",
    ):
        left, right = control_downstream[name], candidate_downstream[name]
        require(
            str(left.dtype) == str(right.dtype) == "torch.bfloat16",
            f"production downstream dtype drift: {name}",
        )
        pairs[name] = _comparison(left, right, torch)
    after = _input_hashes(
        item["routes"], item["weights"], item["shared"], item["route_map"], torch
    )
    all_equal = before == after and all(value["passed"] for value in pairs.values())
    return {
        "fixture_id": item["spec"]["id"],
        "spec": item["spec"],
        "zero_rows": item["zero_rows"],
        "input_hashes_before": before,
        "input_hashes_after": after,
        "comparisons": pairs,
        "all_equal": all_equal,
        "nan_equality_policy": "torch.equal is inapplicable for tensors containing NaNs; raw uint16 equality and identical per-class counts are required",
    }


def _timing_snapshot(
    corpus: list[dict[str, Any]], buffers: dict[str, list[Any]], torch: Any
) -> dict[str, Any]:
    return {
        "inputs": [
            {
                "fixture_id": item["spec"]["id"],
                "routes": _tensor_record(item["routes"], torch),
                "weights": _tensor_record(item["weights"], torch),
                "shared": _tensor_record(item["shared"], torch),
                "route_map": _tensor_record(item["route_map"], torch),
            }
            for item in corpus
        ],
        "outputs": [
            {
                "slot": slot,
                "control_routed": _tensor_record(
                    buffers["control_routed"][slot], torch
                ),
                "control_final": _tensor_record(buffers["control_final"][slot], torch),
                "candidate_final": _tensor_record(
                    buffers["candidate_final"][slot], torch
                ),
                "candidate_repeat": _tensor_record(
                    buffers["candidate_repeat"][slot], torch
                ),
            }
            for slot in range(LAYERS)
        ],
    }


def _timing_storage_proof(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    input_names = ("routes", "weights", "shared", "route_map")
    output_names = (
        "control_routed",
        "control_final",
        "candidate_final",
        "candidate_repeat",
    )
    input_pointers = [
        item[name]["metadata"]["data_ptr"]
        for item in before["inputs"]
        for name in input_names
    ]
    output_pointers = [
        item[name]["metadata"]["data_ptr"]
        for item in before["outputs"]
        for name in output_names
    ]
    require(
        len(set(input_pointers)) == len(input_pointers),
        "timing inputs alias one another",
    )
    require(
        len(set(output_pointers)) == len(output_pointers)
        and set(input_pointers).isdisjoint(output_pointers),
        "timing inputs/outputs alias",
    )
    for left, right in zip(before["outputs"], after["outputs"], strict=True):
        require(left["slot"] == right["slot"], "timing output slot drift")
        for name in output_names:
            require(
                left[name]["metadata"] == right[name]["metadata"],
                f"timing output storage drift: {left['slot']}/{name}",
            )
    return {
        "input_storage_count": len(input_pointers),
        "output_storage_count": len(output_pointers),
        "all_storage_unique_and_nonaliasing": True,
        "input_metadata_and_hashes_unchanged": True,
        "output_metadata_unchanged": True,
    }


def _timing(
    corpus: list[dict[str, Any]],
    expected_final_hashes: dict[str, str],
    packet: dict[str, Any],
    torch: Any,
) -> dict[str, Any]:
    require(len(corpus) >= 256, "timing corpus has fewer than 256 prebuilt fixtures")
    require(
        set(expected_final_hashes) == {item["spec"]["id"] for item in corpus}
        and all(_is_sha(value) for value in expected_final_hashes.values()),
        "timing literal-oracle digest inventory drift",
    )
    buffers = {
        "control_routed": [
            torch.zeros((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
            for _ in range(LAYERS)
        ],
        "control_final": [
            torch.zeros((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
            for _ in range(LAYERS)
        ],
        "candidate_final": [
            torch.zeros((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
            for _ in range(LAYERS)
        ],
        "candidate_repeat": [
            torch.zeros((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
            for _ in range(LAYERS)
        ],
    }
    warm_order = tuple(range(LAYERS))

    def cycle(candidate: bool, fixture_indices: tuple[int, ...]) -> None:
        # This function intentionally performs only the selected native tail op(s).
        for slot, fixture_index in enumerate(fixture_indices):
            item = corpus[fixture_index]
            if candidate:
                _candidate(buffers["candidate_final"][slot], item, torch)
            else:
                _control(
                    buffers["control_routed"][slot],
                    buffers["control_final"][slot],
                    item,
                    torch,
                )

    # Preflight and repeat are outside timed arms; they establish the reuse buffers.
    for slot, fixture_index in enumerate(warm_order):
        item = corpus[fixture_index]
        _control(
            buffers["control_routed"][slot], buffers["control_final"][slot], item, torch
        )
        _candidate(buffers["candidate_final"][slot], item, torch)
        _candidate(buffers["candidate_repeat"][slot], item, torch)
        proof = _comparison(
            buffers["control_final"][slot], buffers["candidate_final"][slot], torch
        )
        repeat = _comparison(
            buffers["candidate_final"][slot], buffers["candidate_repeat"][slot], torch
        )
        require(
            proof["passed"] and repeat["passed"],
            f"timing preflight/repeat mismatch at slot {slot}",
        )
    before = _timing_snapshot(corpus, buffers, torch)
    torch.xpu.synchronize()
    for _ in range(WARM_CYCLES):
        cycle(False, warm_order)
    torch.xpu.synchronize()
    for _ in range(WARM_CYCLES):
        cycle(True, warm_order)
    torch.xpu.synchronize()

    def arm(candidate: bool, fixture_indices: tuple[int, ...]) -> int:
        torch.xpu.synchronize()
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(CYCLES_PER_ARM):
            cycle(candidate, fixture_indices)
        end.record()
        end.synchronize()
        elapsed = round(float(start.elapsed_time(end)) * 1_000_000)
        require(elapsed > 0, "nonpositive timed arm")
        return elapsed

    blocks: list[dict[str, Any]] = []
    timed_block_output_comparisons: list[dict[str, Any]] = []
    for block in range(ABBA_BLOCKS):
        # The prebuilt corpus rotates before, never inside, every timed arm.
        fixture_indices = tuple(
            (block * LAYERS + slot) % len(corpus) for slot in range(LAYERS)
        )
        a1 = arm(False, fixture_indices)
        b1 = arm(True, fixture_indices)
        b2 = arm(True, fixture_indices)
        a2 = arm(False, fixture_indices)
        control_ms = (a1 + a2) / (2 * CYCLES_PER_ARM) / 1e6
        candidate_ms = (b1 + b2) / (2 * CYCLES_PER_ARM) / 1e6
        blocks.append(
            {
                "block": block,
                "fixture_indices": list(fixture_indices),
                "A1_control_elapsed_ns": a1,
                "B1_candidate_elapsed_ns": b1,
                "B2_candidate_elapsed_ns": b2,
                "A2_control_elapsed_ns": a2,
                "paired_control_ms_per_47_layer_cycle": control_ms,
                "paired_candidate_ms_per_47_layer_cycle": candidate_ms,
                "saving_ms_per_47_layer_cycle": control_ms - candidate_ms,
            }
        )
        output_comparisons = []
        for slot, fixture_index in enumerate(fixture_indices):
            fixture_id = corpus[fixture_index]["spec"]["id"]
            comparison = _comparison(
                buffers["control_final"][slot],
                buffers["candidate_final"][slot],
                torch,
            )
            require(
                comparison["passed"]
                and comparison["left_raw_bf16_le_sha256"]
                == expected_final_hashes[fixture_id],
                f"timed block output differs from literal oracle: {block}/{slot}",
            )
            output_comparisons.append(
                {
                    "slot": slot,
                    "fixture_index": fixture_index,
                    "fixture_id": fixture_id,
                    "literal_oracle_raw_bf16_le_sha256": expected_final_hashes[
                        fixture_id
                    ],
                    "control_final_vs_candidate_final": comparison,
                }
            )
        timed_block_output_comparisons.append(
            {"block": block, "outputs": output_comparisons}
        )
    after = _timing_snapshot(corpus, buffers, torch)
    require(before["inputs"] == after["inputs"], "timing input metadata/hash mutation")
    storage_proof = _timing_storage_proof(before, after)
    savings = [block["saving_ms_per_47_layer_cycle"] for block in blocks]
    wins, median = sum(value > 0 for value in savings), statistics.median(savings)
    protocol = packet["protocol"]
    passed = (
        wins >= protocol["minimum_wins"]
        and median >= protocol["minimum_median_saving_ms_per_47_layer_cycle"]
    )
    return {
        "timing_label": "preallocated_incumbent_moe_gather_then_laguna_m8_scale_add_vs_candidate_only",
        "clock": "torch.xpu.Event device elapsed time",
        "warm_cycles_per_arm": WARM_CYCLES,
        "blocks": ABBA_BLOCKS,
        "arm_order": "A-B-B-A",
        "cycles_per_arm": CYCLES_PER_ARM,
        "layers_per_cycle": LAYERS,
        "control_calls_per_primitive_per_arm": CYCLES_PER_ARM * LAYERS,
        "candidate_calls_per_arm": CYCLES_PER_ARM * LAYERS,
        "scheduled_control_selected_launches_per_cycle": 2 * LAYERS,
        "scheduled_candidate_selected_launches_per_cycle": LAYERS,
        "scheduled_fixture_rotation": "prebuilt_outside_timed_arms",
        "synchronization": "arm_boundaries_only",
        "cpu_work_inside_event_interval": "native dispatch calls only",
        "storage_proof": storage_proof,
        "buffer_metadata_and_hash_before": before,
        "buffer_metadata_and_hash_after": after,
        "timed_block_output_comparisons": timed_block_output_comparisons,
        "blocks_detail": blocks,
        "candidate_block_wins": wins,
        "median_saving_ms_per_47_layer_cycle": median,
        "passed_timing_threshold": passed,
        "counter_evidence": "pending_counter_evidence",
    }


def _bind_prior_scale_add_evidence(packet: dict[str, Any]) -> dict[str, Any] | None:
    record = packet.get("prior_incumbent_scale_add_exhaustive_evidence")
    if record is None:
        return None
    require(
        isinstance(record, dict)
        and set(record) == {"path", "sha256", "evidence_id"}
        and _is_sha(record["sha256"])
        and isinstance(record["evidence_id"], str)
        and record["evidence_id"],
        "prior scale/add evidence packet field drift",
    )
    path = _regular_resolved(
        Path(record["path"]), "prior scale/add exhaustive evidence"
    )
    require(
        sha_path(path) == record["sha256"],
        "prior scale/add exhaustive evidence hash drift",
    )
    try:
        evidence = json.loads(path.read_bytes())
    except (TypeError, ValueError) as error:
        raise RuntimeError("prior scale/add exhaustive evidence is not JSON") from error
    require(isinstance(evidence, dict), "prior scale/add evidence is not an object")
    require(
        evidence.get("passed") is True
        or evidence.get("status") in {"pass", "passed", "exhaustive_pass"},
        "prior scale/add exhaustive evidence is not passing",
    )
    return {
        "evidence_id": record["evidence_id"],
        "path": str(path),
        "sha256": record["sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--rank", type=int, required=True)
    args = parser.parse_args()
    authorization = _regular_resolved(args.authorization, "authorization")
    require(args.authorization == authorization, "authorization aliases are forbidden")
    packet, raw_packet = _read_canonical_json(authorization, "authorization")
    packet_sha = sha_bytes(raw_packet)
    card, manifest, manifest_sha, binaries = _validate_packet(
        packet, authorization, args.fixture, args.rank
    )
    runtime_environment = _validate_runner_invocation(card)
    sysfs = _sysfs_binding(card["physical"])
    root = Path(card["output_root"])
    runtime_dirs = seal_runtime_root(root)
    write_canonical(
        root / PREIMPORT,
        {
            "format": "laguna-m8-gather-finalize-preimport-seal-v2",
            "packet_sha256": packet_sha,
            "fixture_manifest_sha256": manifest_sha,
            "rank": args.rank,
            "physical": card["physical"],
            "sysfs": sysfs,
            "evidence_directories": runtime_dirs,
            "runtime_environment": runtime_environment,
            "torch_or_native_imported": False,
        },
    )
    # No torch or native extension import occurs before the durable marker above.
    import torch

    native_modules = _native_imports(torch, binaries)
    binding = _runtime_uuid_binding(torch, card["physical"], sysfs)
    write_canonical(
        root / STARTED,
        {
            "format": "laguna-m8-gather-finalize-tensor-start-v2",
            "packet_sha256": packet_sha,
            "rank": args.rank,
            "tensor_work_started": True,
            "native_modules": native_modules,
        },
    )
    write_canonical(
        root / RUNTIME_BINDING,
        {
            "format": "laguna-m8-gather-finalize-runtime-card-binding-v2",
            "packet_sha256": packet_sha,
            "rank": args.rank,
            "physical": card["physical"],
            "sysfs": sysfs,
            "torch": binding,
        },
    )
    result: dict[str, Any] = {
        "format": "laguna-m8-gather-finalize-component-result-v2",
        "status": "component_failed",
        "passed": False,
        "timing_exactness_passed": False,
        "counter_phase_required": True,
        "counter_phase_complete": False,
        "full_component_pass": False,
        "endpoint_authorized": False,
        "authorization_packet": {"path": str(authorization), "sha256": packet_sha},
        "fixture_manifest": {
            "path": str(args.fixture),
            "sha256": manifest_sha,
            "corpus_version": manifest["corpus_version"],
        },
        "rank": args.rank,
        "physical": card["physical"],
        "runtime_binding": binding,
        "native_modules": native_modules,
        "exactness": {
            "passed": False,
            "nan_equality_policy": "raw uint16 equality and identical classification are required for NaNs; torch.equal is inapplicable",
            "pre_epochs": [],
        },
        "timing": None,
        "post_timing_replay": {"required": True, "passed": False, "epochs": []},
        "integration": {
            "status": "packet_bound_integration_evidence_only",
            "evidence_ids": packet["integration_evidence_ids"],
            "contract": packet["integration_contract"],
        },
        "counter_evidence": "pending_counter_evidence",
        "prior_incumbent_scale_add_exhaustive_evidence": _bind_prior_scale_add_evidence(
            packet
        ),
        "downstream": packet.get("downstream", {}),
        "terminal": {
            "status": "component_failed",
            "passed": False,
            "full_component_pass": False,
        },
    }
    checkpoints = [PREIMPORT, STARTED, RUNTIME_BINDING]
    try:
        specs = _corpus_specs(manifest)
        _validate_spec_coverage(specs)
        expected_hashes = manifest["expected_cpu_input_hashes"]
        require(
            set(expected_hashes) == {spec["id"] for spec in specs},
            "fixture manifest does not bind every generated corpus input",
        )
        finite = _finite_bf16_bits(torch)
        downstream_context = _build_downstream_context(manifest, torch)
        timing_corpus: list[dict[str, Any]] = []
        timing_expected_final_hashes: dict[str, str] = {}
        for epoch, spec in enumerate(specs):
            cpu_item = _make_cpu_fixture(spec, finite, torch)
            cpu_hashes = _validate_cpu_fixture(cpu_item, expected_hashes, torch)
            item = _to_xpu(cpu_item, cpu_hashes, torch)
            epoch_value = _comparison_epoch(item, downstream_context, torch)
            path = root / PRE_EPOCHS / f"epoch-{epoch:03d}.json"
            write_canonical(path, epoch_value)
            checkpoints.append(f"{PRE_EPOCHS}/epoch-{epoch:03d}.json")
            result["exactness"]["pre_epochs"].append(epoch_value)
            timing_expected_final_hashes[spec["id"]] = epoch_value["comparisons"][
                "candidate_production_final_vs_literal_oracle"
            ]["left_raw_bf16_le_sha256"]
            require(
                epoch_value["all_equal"], f"pre-timing exactness mismatch: {spec['id']}"
            )
            timing_corpus.append(item)
        result["exactness"].update(
            passed=True,
            fixture_count=len(specs),
            random_full_fixture_count=sum(
                spec["kind"] == "random_full" for spec in specs
            ),
            finite_bf16_values_per_boundary=FINITE_BF16_COUNT,
            production_rmsnorm_static_input_hashes=downstream_context["static_hashes"],
        )
        timing = _timing(
            timing_corpus,
            timing_expected_final_hashes,
            packet,
            torch,
        )
        result["timing"] = timing
        write_canonical(root / TIMING, timing)
        checkpoints.append(TIMING)
        require(timing["passed_timing_threshold"], "timing threshold failed")
        for epoch, item in enumerate(timing_corpus):
            epoch_value = _comparison_epoch(item, downstream_context, torch)
            path = root / POST_EPOCHS / f"epoch-{epoch:03d}.json"
            write_canonical(path, epoch_value)
            checkpoints.append(f"{POST_EPOCHS}/epoch-{epoch:03d}.json")
            result["post_timing_replay"]["epochs"].append(epoch_value)
            require(
                epoch_value["all_equal"]
                and canonical(epoch_value)
                == canonical(result["exactness"]["pre_epochs"][epoch]),
                f"post-timing replay mismatch: {item['spec']['id']}",
            )
        result["post_timing_replay"]["passed"] = True
        result.update(
            status="component_timing_pass_pending_mandatory_counters",
            passed=True,
            timing_exactness_passed=True,
        )
        result["terminal"] = {
            "status": "component_timing_pass_pending_mandatory_counters",
            "passed": True,
            "full_component_pass": False,
        }
    except BaseException as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    result["checkpoints"] = checkpoints
    result["checkpoint_sha256"] = {
        name: sha_path(root / name) for name in checkpoints if (root / name).is_file()
    }
    write_canonical(root / RESULT, result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
