#!/usr/bin/env python3
"""Fail-closed runtime verifier for the Qwen3.8 A33 full-decode graph arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import tempfile


EXPECTED_LIBCCL = pathlib.Path(
    "/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"
).resolve()
EXPECTED_LIBCCL_SHA256 = (
    "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
)
EXPECTED_KERNEL = pathlib.Path(
    "/home/steve/.venvs/vllm-xpu/lib/ccl/kernels/kernels.spv"
).resolve()
EXPECTED_KERNEL_SHA256 = (
    "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9"
)
OLD_LIBCCL_SHA256 = "ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3"


class VerificationError(RuntimeError):
    pass


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def descendants(root_pid: int) -> list[int]:
    parent_by_pid: dict[int, int] = {}
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
            fields = stat[stat.rfind(") ") + 2 :].split()
            parent_by_pid[int(entry.name)] = int(fields[1])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue

    found = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parent_by_pid.items():
            if parent in found and pid not in found:
                found.add(pid)
                changed = True
    return sorted(found)


def process_environment(pid: int) -> dict[str, str]:
    raw = pathlib.Path(f"/proc/{pid}/environ").read_bytes()
    result: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        result[key.decode(errors="strict")] = value.decode(errors="strict")
    return result


def mapped_libccl(pid: int) -> set[pathlib.Path]:
    mapped: set[pathlib.Path] = set()
    maps = pathlib.Path(f"/proc/{pid}/maps")
    try:
        lines = maps.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return mapped
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) < 6 or "libccl.so.1" not in fields[5]:
            continue
        raw = fields[5]
        if raw.endswith(" (deleted)"):
            raise VerificationError(f"pid {pid} maps a deleted libccl: {raw}")
        mapped.add(pathlib.Path(raw).resolve())
    return mapped


def graph_stats(log: str) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    pattern = re.compile(
        r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*"
        r"([A-Z_]+)\s*\|\s*(\d+)\s*\|"
    )
    for match in pattern.finditer(log):
        rows.append(
            {
                "unpadded_tokens": int(match.group(1)),
                "padded_tokens": int(match.group(2)),
                "paddings": int(match.group(3)),
                "runtime_mode": match.group(4),
                "count": int(match.group(5)),
            }
        )
    return rows


def write_atomic(path: pathlib.Path, payload: dict[str, object]) -> None:
    if path.exists():
        raise VerificationError(f"refusing to overwrite runtime receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-pid", type=int, required=True)
    parser.add_argument("--server-log", type=pathlib.Path, required=True)
    parser.add_argument("--torchinductor-cache", type=pathlib.Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if not pathlib.Path(f"/proc/{args.server_pid}").is_dir():
        raise VerificationError("owned server process is absent")
    if sha256(EXPECTED_LIBCCL) != EXPECTED_LIBCCL_SHA256:
        raise VerificationError("public graph-safe libccl changed")
    if sha256(EXPECTED_KERNEL) != EXPECTED_KERNEL_SHA256:
        raise VerificationError("oneCCL device kernel changed")

    pids = descendants(args.server_pid)
    mapped: list[dict[str, object]] = []
    for pid in pids:
        libraries = mapped_libccl(pid)
        if not libraries:
            continue
        if libraries != {EXPECTED_LIBCCL}:
            raise VerificationError(
                f"pid {pid} maps unexpected libccl paths: {sorted(map(str, libraries))}"
            )
        digest = sha256(EXPECTED_LIBCCL)
        if digest == OLD_LIBCCL_SHA256 or digest != EXPECTED_LIBCCL_SHA256:
            raise VerificationError(f"pid {pid} maps the wrong libccl digest")
        environment = process_environment(pid)
        if environment.get("LD_PRELOAD") != str(EXPECTED_LIBCCL):
            raise VerificationError(f"pid {pid} lacks exact LD_PRELOAD identity")
        if environment.get("CCL_SYCL_ALLREDUCE_LL_THRESHOLD") != "4096":
            raise VerificationError(f"pid {pid} lacks the 4096-byte protocol threshold")
        if environment.get("CCL_KERNEL_PATH") != str(EXPECTED_KERNEL.parent):
            raise VerificationError(f"pid {pid} lacks the exact oneCCL kernel path")
        if environment.get("VLLM_XPU_ENABLE_XPU_GRAPH") != "1":
            raise VerificationError(f"pid {pid} lacks the XPU graph enable selector")
        for forbidden in (
            "XPU_GRAPH",
            "VLLM_XPU_GRAPH",
            "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
            "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
        ):
            if forbidden in environment:
                raise VerificationError(
                    f"pid {pid} carries legacy selector {forbidden}"
                )
        mapped.append(
            {
                "pid": pid,
                "command": pathlib.Path(f"/proc/{pid}/comm")
                .read_text(encoding="utf-8")
                .strip(),
                "path": str(EXPECTED_LIBCCL),
                "sha256": digest,
            }
        )
    if len(mapped) < 4:
        raise VerificationError(
            f"expected at least four collective workers, found {mapped}"
        )

    cache_files = sorted(
        str(path.relative_to(args.torchinductor_cache))
        for path in args.torchinductor_cache.rglob("*")
        if path.is_file()
    )
    if cache_files:
        raise VerificationError(
            f"compilation-free arm populated TorchInductor: {cache_files}"
        )

    log = args.server_log.read_text(encoding="utf-8", errors="replace")
    required_log_fragments = (
        "enforce_eager=False",
        "<CompilationMode.NONE: 0>",
        "<CUDAGraphMode.FULL_DECODE_ONLY: (2, 0)>",
        "'cudagraph_capture_sizes': [1]",
        "'max_cudagraph_capture_size': 1",
        "Graph capturing finished in",
    )
    missing = [fragment for fragment in required_log_fragments if fragment not in log]
    if missing:
        raise VerificationError(f"server log lacks frozen graph receipts: {missing}")
    stats = graph_stats(log)
    full_count = sum(
        int(row["count"])
        for row in stats
        if row["runtime_mode"] == "FULL"
        and row["unpadded_tokens"] == 1
        and row["padded_tokens"] == 1
        and row["paddings"] == 0
    )
    if args.phase == "after" and full_count <= 0:
        raise VerificationError("no size-1 FULL graph runtime dispatch was recorded")

    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "status": "passed",
            "phase": args.phase,
            "server_pid": args.server_pid,
            "descendant_pids": pids,
            "collective_processes": mapped,
            "libccl": {
                "path": str(EXPECTED_LIBCCL),
                "sha256": EXPECTED_LIBCCL_SHA256,
            },
            "ccl_kernel": {
                "path": str(EXPECTED_KERNEL),
                "sha256": EXPECTED_KERNEL_SHA256,
            },
            "torchinductor_files": cache_files,
            "graph_stats": stats,
            "size_1_full_dispatch_count": full_count,
        },
    )


if __name__ == "__main__":
    main()
