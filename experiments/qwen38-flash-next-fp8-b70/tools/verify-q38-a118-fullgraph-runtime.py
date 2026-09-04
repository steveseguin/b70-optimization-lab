"""A118 verifier: the A48 twoshots chain for the MTP1 line with capture sizes [1, 2].

Layers on the frozen A48 verifier (which wraps A46, A43, A37 and the A33 core)
and reproduces every side effect of that chain's main() while replacing the
A37 core with one whose graph receipts expect
cudagraph_capture_sizes [1, 2] and that counts size-1 and size-2 FULL
runtime dispatches. With one speculative token every decode step of a
single sequence is a size-2 verification dispatch, so the after-phase
requires at least one size-2 dispatch and records the size-1 count (which
is zero on this line; A116 showed the size-1 requirement was wrong).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a48-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = "a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8"
EXPECTED_CAPTURE_SIZES = [1, 2]


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A118 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a48_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
A48 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A48)
A46 = A48.BASE
A43 = A46.BASE
A37 = A43.BASE
A36 = A37.BASE
CORE = A37.CORE


def graph_receipts_and_counts(log: str) -> tuple[list[dict[str, object]], int, int]:
    sizes = json.dumps(EXPECTED_CAPTURE_SIZES)
    required_log_fragments = (
        "enforce_eager=False",
        "<CUDAGraphMode.FULL_DECODE_ONLY: (2, 0)>",
        f"'cudagraph_capture_sizes': {sizes}",
        f"'max_cudagraph_capture_size': {max(EXPECTED_CAPTURE_SIZES)}",
        "Graph capturing finished in",
    )
    missing = [fragment for fragment in required_log_fragments if fragment not in log]
    if missing:
        raise CORE.VerificationError(
            f"server log lacks frozen graph receipts: {missing}"
        )
    stats = CORE.graph_stats(log)

    def count(size: int) -> int:
        return sum(
            int(row["count"])
            for row in stats
            if row["runtime_mode"] == "FULL"
            and row["unpadded_tokens"] == size
            and row["padded_tokens"] == size
            and row["paddings"] == 0
        )

    return stats, count(1), count(2)


def core_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-pid", type=int, required=True)
    parser.add_argument("--server-log", type=pathlib.Path, required=True)
    parser.add_argument("--torchinductor-cache", type=pathlib.Path, required=True)
    parser.add_argument("--torch-trace", type=pathlib.Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if not pathlib.Path(f"/proc/{args.server_pid}").is_dir():
        raise CORE.VerificationError("owned server process is absent")
    if CORE.sha256(CORE.EXPECTED_LIBCCL) != CORE.EXPECTED_LIBCCL_SHA256:
        raise CORE.VerificationError("public graph-safe libccl changed")
    if CORE.sha256(CORE.EXPECTED_KERNEL) != CORE.EXPECTED_KERNEL_SHA256:
        raise CORE.VerificationError("oneCCL device kernel changed")

    CORE.process_environment = A36.normalized_environment
    pids = CORE.descendants(args.server_pid)
    mapped: list[dict[str, object]] = []
    for pid in pids:
        libraries = CORE.mapped_libccl(pid)
        if not libraries:
            continue
        if libraries != {CORE.EXPECTED_LIBCCL}:
            raise CORE.VerificationError(
                f"pid {pid} maps unexpected libccl paths: {sorted(map(str, libraries))}"
            )
        digest = CORE.sha256(CORE.EXPECTED_LIBCCL)
        if digest == CORE.OLD_LIBCCL_SHA256 or digest != CORE.EXPECTED_LIBCCL_SHA256:
            raise CORE.VerificationError(f"pid {pid} maps the wrong libccl digest")
        environment = CORE.process_environment(pid)
        if environment.get("TORCH_TRACE") != str(args.torch_trace):
            raise CORE.VerificationError(f"pid {pid} lacks exact Torch trace path")
        if environment.get("LD_PRELOAD") != str(CORE.EXPECTED_LIBCCL):
            raise CORE.VerificationError(f"pid {pid} lacks exact LD_PRELOAD identity")
        if environment.get("CCL_SYCL_ALLREDUCE_LL_THRESHOLD") != "4096":
            raise CORE.VerificationError(
                f"pid {pid} lacks the 4096-byte protocol threshold"
            )
        if environment.get("CCL_KERNEL_PATH") != str(CORE.EXPECTED_KERNEL.parent):
            raise CORE.VerificationError(f"pid {pid} lacks exact oneCCL kernel path")
        if environment.get("VLLM_XPU_ENABLE_XPU_GRAPH") != "1":
            raise CORE.VerificationError(f"pid {pid} lacks XPU graph enable selector")
        for forbidden in (
            "XPU_GRAPH",
            "VLLM_XPU_GRAPH",
            "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
            "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
        ):
            if forbidden in environment:
                raise CORE.VerificationError(
                    f"pid {pid} carries legacy selector {forbidden}"
                )
        mapped.append(
            {
                "pid": pid,
                "command": pathlib.Path(f"/proc/{pid}/comm")
                .read_text(encoding="utf-8")
                .strip(),
                "path": str(CORE.EXPECTED_LIBCCL),
                "sha256": digest,
            }
        )
    if len(mapped) < 4:
        raise CORE.VerificationError(
            f"expected at least four collective workers, found {mapped}"
        )

    log = args.server_log.read_text(encoding="utf-8", errors="replace")
    A37.validate_compile_identity(log)
    stats, size_1_count, size_2_count = graph_receipts_and_counts(log)
    if args.phase == "after" and size_2_count <= 0:
        raise CORE.VerificationError(
            "no size-2 FULL graph runtime dispatch was recorded"
        )

    manifest = A37.cache_manifest(args.torchinductor_cache)
    compile_events = A37.trace_compilations(args.torch_trace)
    CORE.write_atomic(
        args.output,
        {
            "schema_version": 3,
            "status": "passed",
            "phase": args.phase,
            "server_pid": args.server_pid,
            "descendant_pids": pids,
            "collective_processes": mapped,
            "libccl": {
                "path": str(CORE.EXPECTED_LIBCCL),
                "sha256": CORE.EXPECTED_LIBCCL_SHA256,
            },
            "ccl_kernel": {
                "path": str(CORE.EXPECTED_KERNEL),
                "sha256": CORE.EXPECTED_KERNEL_SHA256,
            },
            "compilation_mode": "NONE",
            "inductor_disabled_receipts": log.count(
                "Inductor compilation was disabled by user settings"
            ),
            "torchinductor_cache": {
                "interpretation": "trace_attributed_nested_operator_cache",
                "file_count": len(manifest),
                "total_bytes": sum(int(item["size_bytes"]) for item in manifest),
                "files": manifest,
            },
            "torch_trace": {
                "path": str(args.torch_trace),
                "compile_event_count": len(compile_events),
                "events": compile_events,
            },
            "graph_stats": stats,
            "cudagraph_capture_sizes": EXPECTED_CAPTURE_SIZES,
            "size_1_full_dispatch_count": size_1_count,
            "size_2_full_dispatch_count": size_2_count,
        },
    )


def main() -> None:
    argv = sys.argv[1:]
    server_log = A48.argument_path(argv, "--server-log")
    output = A48.argument_path(argv, "--output")
    A48.validate_algorithm_log(server_log)
    A46.normalized_environment = A48.normalized_environment
    trace = A46.trace_argument(argv)
    A46.validate_rank_trace_files(trace)
    A46.EXPECTED_TRACE = str(trace)
    A46.TRACE_FILES_VALIDATED = True
    A43.normalized_environment = A46.normalized_environment
    A43.EXPECTED_TRACE = A43.trace_argument(argv)
    A36.normalized_environment = A43.normalized_environment
    core_main()
    A48.annotate_output(output)


if __name__ == "__main__":
    main()
