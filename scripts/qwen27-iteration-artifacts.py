#!/usr/bin/env python3
"""Create and admit reusable Qwen27/B70 kernel-iteration artifacts.

All artifacts produced here are diagnostic-only.  They speed focused kernel
development and must never be used as cold-response or decode evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_SPEC = ROOT / "experiments/qwen27-dflash-sycl-b70/harness/model-pack-manifest.json"
DEFAULT_GOLDEN_SPEC = ROOT / "experiments/qwen27-dflash-sycl-b70/harness/golden-corpus-manifest.json"
DEFAULT_RUNTIME = Path("/home/steve/src/llama.cpp")
DEFAULT_BUILD = DEFAULT_RUNTIME / "build-sycl-b70-qwen36-mtp"
DEFAULT_ARTIFACT_ROOT = Path("/mnt/fast-ai/bench-results/qwen27-tp1-worker-harness/iteration-v1")
TOOL_REVISION = 2
CHUNK = 16 * 1024 * 1024
Q4_0_BLOCK_BYTES = 18


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb", buffering=0) as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def hash_tree(path: Path) -> tuple[str, int, list[dict[str, Any]]]:
    if path.is_file():
        sha, size = hash_file(path)
        return sha, size, [{"path": path.name, "sha256": sha, "size_bytes": size}]
    rows: list[dict[str, Any]] = []
    aggregate = hashlib.sha256()
    total = 0
    for candidate in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = candidate.relative_to(path).as_posix()
        sha, size = hash_file(candidate)
        rows.append({"path": relative, "sha256": sha, "size_bytes": size})
        aggregate.update(relative.encode())
        aggregate.update(b"\0")
        aggregate.update(bytes.fromhex(sha))
        total += size
    return aggregate.hexdigest(), total, rows


def command_output(command: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            command, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def runtime_identity(runtime: Path) -> dict[str, Any]:
    commit = command_output(["git", "rev-parse", "HEAD"], runtime)
    diff = command_output(["git", "diff", "--binary", "HEAD"], runtime)
    untracked_text = command_output(
        ["git", "ls-files", "--others", "--exclude-standard"], runtime
    )
    untracked = sorted((untracked_text or "").splitlines())
    digest = hashlib.sha256((diff or "").encode())
    for relative in untracked:
        digest.update(relative.encode())
        digest.update(b"\0")
        candidate = runtime / relative
        if candidate.is_file():
            file_sha, _ = hash_file(candidate)
            digest.update(bytes.fromhex(file_sha))
    dirty = bool(diff or untracked)
    return {
        "path": str(runtime), "commit": commit, "dirty": dirty,
        "dirty_patch_sha256": digest.hexdigest() if dirty else None,
    }


def package_version(name: str) -> str:
    return command_output(["dpkg-query", "-W", "-f=${Version}", name]) or "unknown"


def build_fingerprint(runtime: Path, build: Path) -> dict[str, Any]:
    binaries = {}
    for name in ("test-backend-ops", "llama-bench", "llama-cli", "llama-server"):
        candidate = build / "bin" / name
        if candidate.is_file():
            sha, size = hash_file(candidate)
            binaries[name] = {"path": str(candidate), "sha256": sha, "size_bytes": size}
    cache = build / "CMakeCache.txt"
    cmake = None
    if cache.is_file():
        sha, size = hash_file(cache)
        cmake = {"path": str(cache), "sha256": sha, "size_bytes": size}
    identity = {
        "schema_version": 1,
        "tool_revision": TOOL_REVISION,
        "target_architecture": "bmg-g31",
        "runtime": runtime_identity(runtime),
        "build_dir": str(build),
        "cmake_cache": cmake,
        "binaries": binaries,
        "host": {
            "kernel": platform.release(),
            "intel_opencl_icd": package_version("intel-opencl-icd"),
            "level_zero": package_version("libze-intel-gpu1"),
        },
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    identity["fingerprint_sha256"] = hashlib.sha256(canonical).hexdigest()
    return identity


def deterministic_values(count: int, seed: int, scale: float = 1.0) -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(-scale, scale) for _ in range(count)]


def pack_q4_0(weights: list[float], rows: int, k: int) -> tuple[bytes, list[list[tuple[float, list[int]]]]]:
    out = bytearray()
    decoded: list[list[tuple[float, list[int]]]] = []
    for row in range(rows):
        row_blocks = []
        base = row * k
        for block in range(k // 32):
            values = weights[base + block * 32:base + (block + 1) * 32]
            maximum = max(abs(value) for value in values) or 1.0
            d = maximum / 7.0
            q = [max(-8, min(7, round(value / d))) for value in values]
            # The half conversion is part of the on-disk contract; reference
            # arithmetic must use the rounded half value as kernels do.
            d_half = struct.unpack("<e", struct.pack("<e", d))[0]
            out.extend(struct.pack("<e", d_half))
            out.extend(bytes((q[j] + 8) | ((q[j + 16] + 8) << 4) for j in range(16)))
            row_blocks.append((d_half, q))
        decoded.append(row_blocks)
    return bytes(out), decoded


def pack_q8_1(values: list[float], m: int, k: int) -> tuple[bytes, list[list[tuple[float, list[int]]]]]:
    out = bytearray()
    decoded = []
    for column in range(m):
        column_blocks = []
        base = column * k
        for block in range(k // 32):
            source = values[base + block * 32:base + (block + 1) * 32]
            maximum = max(abs(value) for value in source) or 1.0
            d = maximum / 127.0
            q = [max(-128, min(127, round(value / d))) for value in source]
            d_half = struct.unpack("<e", struct.pack("<e", d))[0]
            s_half = struct.unpack("<e", struct.pack("<e", d_half * sum(q)))[0]
            out.extend(struct.pack("<ee", d_half, s_half))
            out.extend(struct.pack("<32b", *q))
            column_blocks.append((d_half, q))
        decoded.append(column_blocks)
    return bytes(out), decoded


def reference_dot(
    weights: list[list[tuple[float, list[int]]]],
    inputs: list[list[tuple[float, list[int]]]],
) -> bytes:
    result = bytearray()
    for column in inputs:
        for row in weights:
            value = 0.0
            for (wd, wq), (xd, xq) in zip(row, column):
                value += wd * xd * sum(a * b for a, b in zip(wq, xq))
            result.extend(struct.pack("<f", value))
    return bytes(result)


def write_tensor(path: Path, data: bytes, dtype: str, shape: list[int]) -> dict[str, Any]:
    path.write_bytes(data)
    sha, size = hash_file(path)
    return {
        "path": path.name, "dtype": dtype, "shape": shape,
        "size_bytes": size, "sha256": sha,
    }


def prepare_golden(args: argparse.Namespace) -> int:
    spec = load_json(args.golden_spec)
    widths = spec["required_widths"]
    root = args.artifact_root / "golden" / "mmvq-q4_0-q8_1-v1"
    root.mkdir(parents=True, exist_ok=True)
    k, n = args.k, args.n
    weights_raw = deterministic_values(n * k, args.seed, 0.75)
    weight_bytes, decoded_weights = pack_q4_0(weights_raw, n, k)
    tensors = [write_tensor(root / "weights.q4_0.bin", weight_bytes, "q4_0", [n, k])]
    cases = []
    for m in widths:
        raw = deterministic_values(m * k, args.seed + m, 1.25)
        input_bytes, decoded_inputs = pack_q8_1(raw, m, k)
        expected = reference_dot(decoded_weights, decoded_inputs)
        case_tensors = [
            write_tensor(root / f"input-m{m}.q8_1.bin", input_bytes, "q8_1", [m, k]),
            write_tensor(root / f"expected-m{m}.f32.bin", expected, "f32", [m, n]),
        ]
        tensors.extend(case_tensors)
        cases.append({"width": m, "tensors": [item["path"] for item in case_tensors]})
    fingerprint = build_fingerprint(args.runtime, args.build)
    model_spec = load_json(args.model_spec)
    manifest = {
        "schema_version": 1,
        "format": "qwen27-mmvp-q4_0-q8_1-golden-v1",
        "status": "ready",
        "evidence_class": "synthetic-kernel-contract-diagnostic-only",
        "promotion_eligible": False,
        "created_unix": time.time(),
        "generator": {"path": str(Path(__file__).resolve()), "revision": TOOL_REVISION},
        "source_model_sha256": model_spec["source"]["sha256"],
        "note": "Representative deterministic packed tensors; not captured model activations.",
        "seed": args.seed,
        "k": k,
        "n": n,
        "required_widths": widths,
        "cases": cases,
        "tensors": tensors,
        "build_fingerprint_sha256": fingerprint["fingerprint_sha256"],
    }
    atomic_json(root / "manifest.json", manifest)
    print(json.dumps({"status": "ready", "root": str(root), "tensors": len(tensors)}, indent=2))
    return 0


def verify_golden(args: argparse.Namespace) -> int:
    root = args.artifact_root / "golden" / "mmvq-q4_0-q8_1-v1"
    manifest = load_json(root / "manifest.json")
    failures = []
    for tensor in manifest["tensors"]:
        candidate = root / tensor["path"]
        if not candidate.is_file():
            failures.append(f"missing:{tensor['path']}")
            continue
        sha, size = hash_file(candidate)
        if sha != tensor["sha256"] or size != tensor["size_bytes"]:
            failures.append(f"identity:{tensor['path']}")
    status = {"status": "failed" if failures else "ready", "root": str(root), "failures": failures}
    print(json.dumps(status, indent=2))
    return 1 if failures else 0


def pack_key(model_sha: str, packer: str, layout: str, artifact_sha: str) -> str:
    value = f"{model_sha}\0{packer}\0{layout}\0{artifact_sha}".encode()
    return hashlib.sha256(value).hexdigest()


def canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def q4_joint_n_pack(source: bytes, rows: int, k: int, n_tile: int) -> bytes:
    """Pack GGML Q4_0 blocks jointly across N rows.

    Input is ordinary row-major GGML Q4_0: fp16 scale then 16 nibble bytes for
    every 32 K values.  Output walks K blocks first, then N tiles.  Within a
    tile it stores all N scales followed by byte-position-major quant bytes.
    The last N tile is zero padded.  This is deliberately reversible and does
    not silently depend on a compiler structure layout.
    """
    if rows <= 0 or k <= 0 or k % 32 or n_tile <= 0:
        raise ValueError("rows and k must be positive, k divisible by 32, and n-tile positive")
    blocks_k = k // 32
    expected = rows * blocks_k * Q4_0_BLOCK_BYTES
    if len(source) != expected:
        raise ValueError(f"Q4_0 payload is {len(source)} bytes; expected {expected}")
    out = bytearray()
    for kb in range(blocks_k):
        for row0 in range(0, rows, n_tile):
            blocks = []
            for lane in range(n_tile):
                row = row0 + lane
                if row < rows:
                    offset = (row * blocks_k + kb) * Q4_0_BLOCK_BYTES
                    blocks.append(source[offset:offset + Q4_0_BLOCK_BYTES])
                else:
                    blocks.append(bytes(Q4_0_BLOCK_BYTES))
            for block in blocks:
                out.extend(block[:2])
            for byte_index in range(16):
                for block in blocks:
                    out.append(block[2 + byte_index])
    return bytes(out)


def q4_joint_n_unpack(packed: bytes, rows: int, k: int, n_tile: int) -> bytes:
    blocks_k = k // 32
    tiles_n = math.ceil(rows / n_tile)
    tile_bytes = n_tile * Q4_0_BLOCK_BYTES
    expected = blocks_k * tiles_n * tile_bytes
    if len(packed) != expected:
        raise ValueError(f"joint-N payload is {len(packed)} bytes; expected {expected}")
    out = bytearray(rows * blocks_k * Q4_0_BLOCK_BYTES)
    cursor = 0
    for kb in range(blocks_k):
        for row0 in range(0, rows, n_tile):
            scales = packed[cursor:cursor + 2 * n_tile]
            cursor += 2 * n_tile
            quants = packed[cursor:cursor + 16 * n_tile]
            cursor += 16 * n_tile
            for lane in range(n_tile):
                row = row0 + lane
                if row >= rows:
                    continue
                offset = (row * blocks_k + kb) * Q4_0_BLOCK_BYTES
                out[offset:offset + 2] = scales[2 * lane:2 * lane + 2]
                out[offset + 2:offset + 18] = bytes(
                    quants[byte_index * n_tile + lane] for byte_index in range(16)
                )
    return bytes(out)


def pack_q4_payload(args: argparse.Namespace) -> int:
    source = args.tensor_payload.resolve()
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    spec = load_json(args.model_spec)
    fingerprint = build_fingerprint(args.runtime, args.build)
    layout = {
        "name": "q4_0-joint-n-v1", "n_tile": args.n_tile,
        "source_block": "ggml-q4_0-fp16-scale-plus-16-nibble-bytes",
        "order": "kblock,n_tile,scales[n],quant_byte[16][n]",
        "padding": "zero lanes to n_tile",
    }
    identity = {
        "source_model_sha256": spec["source"]["sha256"],
        "tensor_name": args.tensor_name, "source_tensor_sha256": source_sha,
        "shape": [args.rows, args.k], "layout": layout,
        "packer_revision": TOOL_REVISION,
        "compiler_fingerprint": fingerprint["fingerprint_sha256"],
        "device": args.device,
    }
    key = canonical_sha(identity)
    final = args.artifact_root / "xe2-verifier-packs" / key
    if final.exists():
        manifest = load_json(final / "manifest.json")
        if manifest.get("key") != key or manifest.get("identity") != identity:
            raise RuntimeError(f"existing pack identity does not match requested pack: {final}")
        payload = final / manifest["payload"]["path"]
        sha, size = hash_file(payload)
        if sha != manifest["payload"]["sha256"] or size != manifest["payload"]["size_bytes"]:
            raise RuntimeError(f"existing pack failed checksum validation: {final}")
        print(json.dumps({"status": "reused", "key": key, "manifest": str(final / "manifest.json")}, indent=2))
        return 0
    packed = q4_joint_n_pack(source_bytes, args.rows, args.k, args.n_tile)
    if q4_joint_n_unpack(packed, args.rows, args.k, args.n_tile) != source_bytes:
        raise RuntimeError("internal joint-N round-trip validation failed")
    staging = final.with_name(f".{key}.tmp-{os.getpid()}")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        payload_path = staging / "weights.q4_0.joint-n.bin"
        payload_path.write_bytes(packed)
        payload_sha, payload_size = hash_file(payload_path)
        manifest = {
            "schema_version": 1, "format": "qwen27-xe2-verifier-tensor-pack-v1",
            "status": "ready", "evidence_class": "development-iteration-only",
            "promotion_eligible": False, "key": key, "identity": identity,
            "source": {"payload_path": str(source), "sha256": source_sha,
                       "size_bytes": len(source_bytes), "container": "extracted-gguf-tensor-payload"},
            "payload": {"path": payload_path.name, "sha256": payload_sha,
                        "size_bytes": payload_size},
            "loader_contract": {"lookup_key": key, "manifest": "manifest.json",
                                "required_validation": ["identity-key", "payload-sha256", "payload-size"],
                                "mmap_safe": True, "endianness": "little"},
            "validation": {"round_trip_exact": True}, "created_unix": time.time(),
        }
        atomic_json(staging / "manifest.json", manifest)
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps({"status": "ready", "key": key, "manifest": str(final / "manifest.json")}, indent=2))
    return 0


def verify_q4_payload(args: argparse.Namespace) -> int:
    root = args.artifact_root / "xe2-verifier-packs" / args.pack_key
    manifest = load_json(root / "manifest.json")
    failures = []
    if canonical_sha(manifest["identity"]) != manifest["key"] or manifest["key"] != args.pack_key:
        failures.append("identity-key")
    payload = root / manifest["payload"]["path"]
    if not payload.is_file():
        failures.append("payload-missing")
    else:
        sha, size = hash_file(payload)
        if sha != manifest["payload"]["sha256"] or size != manifest["payload"]["size_bytes"]:
            failures.append("payload-identity")
    print(json.dumps({"status": "failed" if failures else "ready", "key": args.pack_key,
                      "manifest": str(root / "manifest.json"), "failures": failures}, indent=2))
    return 1 if failures else 0


def register_pack(args: argparse.Namespace) -> int:
    artifact = args.pack_artifact.resolve()
    if not artifact.exists():
        raise FileNotFoundError(artifact)
    artifact_sha, size, files = hash_tree(artifact)
    spec = load_json(args.model_spec)
    fingerprint = build_fingerprint(args.runtime, args.build)
    key = pack_key(spec["source"]["sha256"], args.packer_revision, args.layout, artifact_sha)
    registry = args.artifact_root / "packs" / key
    manifest = {
        "schema_version": 1,
        "format": "qwen27-b70-offline-pack-registry-v1",
        "status": "admitted",
        "evidence_class": "development-iteration-only",
        "promotion_eligible": False,
        "key": key,
        "source_model_sha256": spec["source"]["sha256"],
        "artifact": {"path": str(artifact), "sha256": artifact_sha, "size_bytes": size, "files": files},
        "packer_revision": args.packer_revision,
        "layout": args.layout,
        "kernel_abi": args.kernel_abi,
        "build_fingerprint_sha256": fingerprint["fingerprint_sha256"],
        "created_unix": time.time(),
        "binding_status": "external-artifact-registered-loader-binding-required",
    }
    atomic_json(registry / "manifest.json", manifest)
    print(json.dumps({"status": "admitted", "key": key, "manifest": str(registry / 'manifest.json')}, indent=2))
    return 0


def verify_pack(args: argparse.Namespace) -> int:
    manifest_path = args.artifact_root / "packs" / args.pack_key / "manifest.json"
    manifest = load_json(manifest_path)
    artifact = Path(manifest["artifact"]["path"])
    actual_sha, actual_size, _ = hash_tree(artifact)
    okay = actual_sha == manifest["artifact"]["sha256"] and actual_size == manifest["artifact"]["size_bytes"]
    print(json.dumps({"status": "admitted" if okay else "failed", "key": args.pack_key, "artifact": str(artifact)}, indent=2))
    return 0 if okay else 1


def run_focused(args: argparse.Namespace) -> int:
    fingerprint = build_fingerprint(args.runtime, args.build)
    golden_rc = verify_golden(args)
    if golden_rc:
        return golden_rc
    binary = args.build / "bin" / "test-backend-ops"
    if not binary.is_file():
        raise FileNotFoundError(binary)
    ops = args.ops or [
        "MUL_MAT_Q4_0_REORDER", "SWIGLU_MMVQ_ADD",
        "MMVQ_ADD_RMS_Q8_MMVQ_ADD",
    ]
    identity = {
        "fingerprint": fingerprint["fingerprint_sha256"], "gpu": args.gpu,
        "ops": ops, "environment": args.env,
    }
    run_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    result_dir = args.artifact_root / "focused-runs" / run_key
    result_path = result_dir / "result.json"
    if args.reuse_pass and result_path.is_file():
        old = load_json(result_path)
        if old.get("passed") is True:
            print(json.dumps({"status": "reused-pass", "run_key": run_key, "result": str(result_path)}, indent=2))
            return 0
    result_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ZE_AFFINITY_MASK"] = args.gpu
    for item in args.env:
        name, separator, value = item.partition("=")
        if not separator or not name:
            raise ValueError(f"invalid --env {item!r}; expected NAME=VALUE")
        env[name] = value
    logs = []
    passed = True
    started = time.monotonic()
    for op in ops:
        command = [str(binary), "test", "-b", "SYCL0", "-o", op]
        result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = result_dir / f"{op.lower()}.log"
        log.write_text(result.stdout, encoding="utf-8")
        logs.append({"op": op, "returncode": result.returncode, "log": str(log)})
        passed &= result.returncode == 0
    record = {
        "schema_version": 1, "passed": passed, "run_key": run_key,
        "evidence_class": "focused-diagnostic-only", "promotion_eligible": False,
        "seconds": time.monotonic() - started, "identity": identity,
        "build_fingerprint": fingerprint, "logs": logs,
    }
    atomic_json(result_path, record)
    print(json.dumps({"status": "passed" if passed else "failed", "run_key": run_key, "result": str(result_path)}, indent=2))
    return 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fingerprint", "golden-prepare", "golden-verify", "pack-register", "pack-verify", "q4-pack", "q4-verify", "focused"))
    parser.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)
    parser.add_argument("--golden-spec", type=Path, default=DEFAULT_GOLDEN_SPEC)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--seed", type=int, default=270036)
    parser.add_argument("--k", type=int, default=5120)
    parser.add_argument("--n", type=int, default=256)
    parser.add_argument("--pack-artifact", type=Path)
    parser.add_argument("--pack-key")
    parser.add_argument("--tensor-payload", type=Path)
    parser.add_argument("--tensor-name")
    parser.add_argument("--rows", type=int)
    parser.add_argument("--n-tile", type=int, default=8)
    parser.add_argument("--device", default="intel-bmg-g31")
    parser.add_argument("--packer-revision", default="unspecified")
    parser.add_argument("--layout", default="q4_0-runtime-reorder-compatible")
    parser.add_argument("--kernel-abi", default="qwen27-b70-pack-v1")
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--op", dest="ops", action="append")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--reuse-pass", action="store_true")
    args = parser.parse_args()
    if args.command == "pack-register" and args.pack_artifact is None:
        parser.error("pack-register requires --pack-artifact")
    if args.command == "pack-verify" and not args.pack_key:
        parser.error("pack-verify requires --pack-key")
    if args.command == "q4-pack" and (args.tensor_payload is None or not args.tensor_name or args.rows is None):
        parser.error("q4-pack requires --tensor-payload, --tensor-name, and --rows")
    if args.command == "q4-verify" and not args.pack_key:
        parser.error("q4-verify requires --pack-key")
    if args.k % 32:
        parser.error("--k must be divisible by 32")
    return args


def main() -> int:
    args = parse_args()
    if args.command == "fingerprint":
        print(json.dumps(build_fingerprint(args.runtime, args.build), indent=2, sort_keys=True))
        return 0
    if args.command == "golden-prepare":
        return prepare_golden(args)
    if args.command == "golden-verify":
        return verify_golden(args)
    if args.command == "pack-register":
        return register_pack(args)
    if args.command == "pack-verify":
        return verify_pack(args)
    if args.command == "q4-pack":
        return pack_q4_payload(args)
    if args.command == "q4-verify":
        return verify_q4_payload(args)
    if args.command == "focused":
        return run_focused(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
