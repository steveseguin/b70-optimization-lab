#!/usr/bin/env python3
"""A37 map-authoritative verifier with mode-NONE-aware cache evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib


BASE_PATH = pathlib.Path(__file__).with_name("verify-q38-a36-fullgraph-runtime.py")
EXPECTED_BASE_SHA256 = (
    "256de72996103f284635c7402ceaa3d41ac8af877aabe773a1af10a84f09ae16"
)


def verify_base_hash(path: pathlib.Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"A37 base verifier hash changed: expected {expected}, found {digest}"
        )


verify_base_hash(BASE_PATH, EXPECTED_BASE_SHA256)
SPEC = importlib.util.spec_from_file_location("q38_a36_runtime_verifier", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
CORE = BASE.BASE.BASE

ALLOWED_COMPILED_TARGETS = {
    (
        "/home/steve/src/vllm-current-main/vllm/model_executor/layers/"
        "vocab_parallel_embedding.py",
        "get_masked_input_and_mask",
        168,
    ): "016bcb89432f68d0b8d6b88fb7b1f50d168cda6237c4c4397cf8dbe62910ad75",
    (
        "/home/steve/src/vllm-current-main/vllm/model_executor/layers/mamba/gdn/"
        "qwen_gdn_linear_attn.py",
        "prepare_gdn_attention_core_inputs",
        665,
    ): "8efb71ec46bd874d4eafa267149e5571ccac1488b5053763956961598d4b5fe7",
}


def cache_manifest(root: pathlib.Path) -> list[dict[str, int | str]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def validate_compile_identity(log: str) -> None:
    required = (
        "<CompilationMode.NONE: 0>",
        "Inductor compilation was disabled by user settings",
    )
    missing = [item for item in required if item not in log]
    if missing:
        raise CORE.VerificationError(
            f"server log lacks compilation-free receipts: {missing}"
        )
    forbidden = (
        "Compiling a graph for compile range",
        "torch.compile took",
    )
    present = [item for item in forbidden if item in log]
    if present:
        raise CORE.VerificationError(
            f"server log reports forbidden model compilation: {present}"
        )


def trace_compilations(root: pathlib.Path) -> list[dict[str, int | str]]:
    logs = sorted(root.glob("dedicated_log_torch_trace*.log"))
    if not logs:
        raise CORE.VerificationError(f"Torch trace logs are absent under {root}")

    events: list[dict[str, int | str]] = []
    for log_path in logs:
        interned: dict[int, str] = {}
        for line_number, line in enumerate(
            log_path.read_text(encoding="utf-8", errors="strict").splitlines(), 1
        ):
            json_start = line.find("{")
            if json_start < 0:
                if not line or line.startswith("\t"):
                    continue
                raise CORE.VerificationError(
                    f"unparseable Torch trace record {log_path}:{line_number}"
                )
            try:
                record = json.loads(line[json_start:])
            except json.JSONDecodeError:
                if line.startswith("\t"):
                    continue
                raise CORE.VerificationError(
                    f"unparseable Torch trace record {log_path}:{line_number}"
                ) from None
            if "str" in record:
                value, identifier = record["str"]
                interned[int(identifier)] = str(value)
                continue
            if "dynamo_start" not in record:
                continue
            stack = record["dynamo_start"].get("stack", [])
            if not stack:
                raise CORE.VerificationError(
                    f"Torch trace has stackless dynamo_start at {log_path}:{line_number}"
                )
            target = stack[-1]
            filename_id = int(target["filename"])
            if filename_id not in interned:
                raise CORE.VerificationError(
                    f"Torch trace has unresolved filename {filename_id} at "
                    f"{log_path}:{line_number}"
                )
            filename = str(pathlib.Path(interned[filename_id]).resolve())
            name = str(target["name"])
            first_line = int(target["line"])
            identity = (filename, name, first_line)
            expected_sha256 = ALLOWED_COMPILED_TARGETS.get(identity)
            if expected_sha256 is None:
                raise CORE.VerificationError(
                    f"unexpected compiled target {identity} at {log_path}:{line_number}"
                )
            if CORE.sha256(pathlib.Path(filename)) != expected_sha256:
                raise CORE.VerificationError(
                    f"compiled target source changed for {identity}"
                )
            events.append(
                {
                    "trace_file": log_path.name,
                    "trace_line": line_number,
                    "filename": filename,
                    "name": name,
                    "first_line": first_line,
                    "source_sha256": expected_sha256,
                }
            )
    if not events:
        raise CORE.VerificationError("Torch trace contains no dynamo_start events")
    return events


def main() -> None:
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

    CORE.process_environment = BASE.normalized_environment
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
    validate_compile_identity(log)
    required_log_fragments = (
        "enforce_eager=False",
        "<CUDAGraphMode.FULL_DECODE_ONLY: (2, 0)>",
        "'cudagraph_capture_sizes': [1]",
        "'max_cudagraph_capture_size': 1",
        "Graph capturing finished in",
    )
    missing = [fragment for fragment in required_log_fragments if fragment not in log]
    if missing:
        raise CORE.VerificationError(
            f"server log lacks frozen graph receipts: {missing}"
        )

    stats = CORE.graph_stats(log)
    full_count = sum(
        int(row["count"])
        for row in stats
        if row["runtime_mode"] == "FULL"
        and row["unpadded_tokens"] == 1
        and row["padded_tokens"] == 1
        and row["paddings"] == 0
    )
    if args.phase == "after" and full_count <= 0:
        raise CORE.VerificationError(
            "no size-1 FULL graph runtime dispatch was recorded"
        )

    manifest = cache_manifest(args.torchinductor_cache)
    compile_events = trace_compilations(args.torch_trace)
    CORE.write_atomic(
        args.output,
        {
            "schema_version": 2,
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
            "size_1_full_dispatch_count": full_count,
        },
    )


if __name__ == "__main__":
    main()
