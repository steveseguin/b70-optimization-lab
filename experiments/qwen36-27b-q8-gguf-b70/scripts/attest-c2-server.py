#!/usr/bin/env python3
"""Attest the sealed Qwen3.6 27B Q8 c2 server identity from launch logs.

This is the standalone form of the attestation contract embedded in
``run-c2-validation.sh``.  It deliberately emits the same JSON shape so a
diagnostic runner can reuse the sealed c2 identity without changing the formal
runner.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"[0-9a-f]{64}")


def context_value(text: str, name: str) -> str | None:
    values = re.findall(
        rf"llama_context:\s+{re.escape(name)}\s*=\s*([^\s]+)", text
    )
    return values[-1] if values else None


def build_attestation(
    server_text: str,
    identity_text: str,
    model_size: int,
    runtime_sha256: str,
    minimum_fit_free_mib: int,
) -> dict[str, Any]:
    """Return the exact c2 attestation object used by the formal runner."""

    identity_header = identity_text.split("--- server ---", 1)[0]
    identity: dict[str, str] = {}
    for line in identity_header.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            identity[key] = value

    expected_identity = {
        "model_bytes": str(model_size),
        "model_alias": "qwen36-27b-q8_0-target-only",
        "llama_server_sha256": runtime_sha256,
        "ctx_size": "65536",
        "parallel_slots": "2",
        "ctx_size_per_slot": "32768",
        "kv_unified": "0",
        "cont_batching": "1",
        "batch_size": "1024",
        "ubatch_size": "128",
        "n_gpu_layers": "99",
        "threads": "8",
        "http_threads": "6",
        "log_verbosity": "4",
        "flash_attn": "on",
        "cache_type_k": "f16",
        "cache_type_v": "f16",
        "speculation": "none",
        "vision_projector": "none",
        "reasoning": "off",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
        "GGML_SYCL_ENABLE_VMM": "1",
        "GGML_SYCL_ENABLE_GRAPH": "0",
        "GGML_SYCL_ENABLE_DNN": "0",
        "GGML_SYCL_ENABLE_OPT": "1",
        "GGML_SYCL_FA_ONEDNN": "1",
        "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
        "GGML_SYCL_ENABLE_MKL_FA": "1",
        "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
    }
    identity_fields = {
        key: identity.get(key) == value for key, value in expected_identity.items()
    }
    model_fd = identity.get("model_pinned_fd", "")
    identity_fields["pinned_model_fd_contract"] = (
        model_fd.isdigit()
        and identity.get("model_load_path") == f"/proc/self/fd/{model_fd}"
        and str(identity.get("model_pinned_path", "")).startswith("/")
    )

    argv = identity.get("argv", "")
    required_argv = (
        "-ngl 99",
        "-c 65536",
        "-np 2",
        "-b 1024",
        "-ub 128",
        "-ctk f16",
        "-ctv f16",
        "-fa on",
        "--spec-type none",
        "--reasoning off",
        "--ctx-checkpoints 0",
        "--cache-ram 0",
        "--no-cache-idle-slots",
        "--no-context-shift",
        "--no-kv-unified",
        "--cont-batching",
        "--slots",
        "--metrics",
        "--threads-http 6",
        "--jinja",
    )
    argv_fields = {value: value in argv for value in required_argv}

    offload_pairs = [
        (int(left), int(right))
        for left, right in re.findall(
            r"offloaded\s+(\d+)/(\d+)\s+layers to GPU", server_text
        )
    ]
    slot_matches = re.findall(
        r"initializing, n_slots = (\d+), n_ctx_slot = (\d+), kv_unified = '([^']+)'",
        server_text,
    )
    kv_matches = re.findall(
        r"llama_kv_cache: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+)/(\d+) seqs\), K \(([^)]+)\):\s*([0-9.]+) MiB, V \(([^)]+)\):\s*([0-9.]+) MiB",
        server_text,
    )
    recurrent_matches = re.findall(
        r"llama_memory_recurrent: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+) seqs",
        server_text,
    )
    fit_matches = [
        (int(free), int(required))
        for free, required in re.findall(
            r"will leave\s+(\d+)\s+>=\s+(\d+) MiB of free device memory",
            server_text,
        )
    ]
    kv = kv_matches[-1] if kv_matches else None
    recurrent = recurrent_matches[-1] if recurrent_matches else None
    fit_free_mib = fit_matches[-1][0] if fit_matches else None
    runtime_fields = {
        "full_offload_65_of_65": (65, 65) in offload_pairs,
        "n_seq_max_2": context_value(server_text, "n_seq_max") == "2",
        "n_ctx_65536": context_value(server_text, "n_ctx") == "65536",
        "n_ctx_seq_32768": context_value(server_text, "n_ctx_seq") == "32768",
        "n_batch_1024": context_value(server_text, "n_batch") == "1024",
        "n_ubatch_128": context_value(server_text, "n_ubatch") == "128",
        "flash_attn_enabled": context_value(server_text, "flash_attn")
        == "enabled",
        "kv_unified_false": context_value(server_text, "kv_unified") == "false",
        "two_slot_runtime": bool(slot_matches)
        and slot_matches[-1] == ("2", "32768", "false"),
        # Non-unified KV reports per-sequence cell capacity followed by the
        # maximum/current sequence counts.  Together these fields attest the
        # full two-slot 4-GiB allocation.
        "f16_kv_4096_mib": bool(kv)
        and abs(float(kv[0]) - 4096.0) <= 0.1
        and kv[1:5] == ("32768", "16", "2", "2")
        and kv[5] == "f16"
        and abs(float(kv[6]) - 2048.0) <= 0.1
        and kv[7] == "f16"
        and abs(float(kv[8]) - 2048.0) <= 0.1,
        "two_slot_recurrent_state": bool(recurrent)
        and 298.0 <= float(recurrent[0]) <= 301.0
        and recurrent[1:] == ("2", "64", "2"),
        "post_fit_free_at_least_minimum": isinstance(fit_free_mib, int)
        and fit_free_mib >= minimum_fit_free_mib,
        "prompt_cache_disabled": "prompt cache is disabled" in server_text,
        "context_checkpoints_disabled": "context checkpoints disabled"
        in server_text,
        "speculation_disabled": (
            "no implementations specified for speculative decoding" in server_text
        ),
    }
    result: dict[str, Any] = {
        "expected_identity": expected_identity,
        "identity_fields": identity_fields,
        "argv_fields": argv_fields,
        "runtime_fields": runtime_fields,
        "observed": {
            "offload_pairs": offload_pairs,
            "slot_config": slot_matches[-1] if slot_matches else None,
            "kv_config": kv,
            "recurrent_config": recurrent,
            "fit_free_mib": fit_free_mib,
            "minimum_fit_free_mib": minimum_fit_free_mib,
        },
    }
    result["passed"] = (
        all(identity_fields.values())
        and all(argv_fields.values())
        and all(runtime_fields.values())
    )
    return result


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing output: {path}")
    if not path.parent.is_dir():
        raise SystemExit(f"output parent is not a directory: {path.parent}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--identity-log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-size", type=int, required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--minimum-fit-free-mib", type=int, default=1024)
    args = parser.parse_args()

    for label, path in (
        ("server log", args.server_log),
        ("identity log", args.identity_log),
    ):
        if not path.is_file():
            parser.error(f"{label} is not a file: {path}")
    if args.out.resolve() in {
        args.server_log.resolve(),
        args.identity_log.resolve(),
    }:
        parser.error("output must not overwrite an input")
    if args.model_size <= 0:
        parser.error("--model-size must be positive")
    if not SHA256_RE.fullmatch(args.runtime_sha256):
        parser.error("--runtime-sha256 must be a lowercase SHA-256 digest")
    if args.minimum_fit_free_mib < 1024:
        parser.error("--minimum-fit-free-mib cannot be below 1024")

    result = build_attestation(
        args.server_log.read_text(errors="replace"),
        args.identity_log.read_text(errors="replace"),
        args.model_size,
        args.runtime_sha256,
        args.minimum_fit_free_mib,
    )
    write_json_exclusive(args.out, result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
