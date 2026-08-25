#!/usr/bin/env python3
"""Static contract and exact-base applicability check for the fa0 graph port."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PATCH = REPO / "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-evidence-port-20260825.patch"
BASE = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
SHA256 = "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892"
PATHS = {
    "ggml/src/ggml-sycl/common.hpp",
    "ggml/src/ggml-sycl/ggml-sycl.cpp",
}
BASE_HASHES = {
    "ggml/src/ggml-sycl/common.hpp": "25e2323e6199c25b840c4c2f5729389963358faa892de1ee6b71a08619ac7be8",
    "ggml/src/ggml-sycl/ggml-sycl.cpp": "561a275ca5abfc437fdbf126a5d1b475755558d6cec9cac3f5f66d1af8c241bd",
}


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def static_contract() -> None:
    raw = PATCH.read_bytes()
    text = raw.decode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == SHA256

    headers = {
        line.removeprefix("+++ b/")
        for line in text.splitlines()
        if line.startswith("+++ b/")
    }
    assert headers == PATHS, headers

    required = (
        "GGML_SYCL_GRAPH_CACHE_SIZE",
        "std::max(0, std::min(g_ggml_sycl_graph_cache_size, 64))",
        "graph_signature_append_tensor",
        "[SYCL-GRAPH] requested",
        "[SYCL-GRAPH] recording_entered",
        "[SYCL-GRAPH] direct_replay",
        "[SYCL-GRAPH] replayed",
        "[SYCL-GRAPH] summary",
        "cache_entries=%zu cache_limit=%d",
        "case GGML_OP_CONCAT: {",
        "dim != 3 || !ggml_is_contiguous(node->src[0])",
        "NOTE (per-device graphs)",
    )
    for marker in required:
        assert marker in text, marker

    forbidden = (
        "+    if (ggml_sycl_info().device_count > 1)",
        "SYCL-CYCLE",
        "server-context.cpp",
        "gated_delta_net.cpp",
        "mmvq.cpp",
        "src/llama-context.cpp",
    )
    for marker in forbidden:
        assert marker not in text, marker


def exact_source_check(source: Path) -> None:
    assert source.is_dir(), source
    assert run("git", "rev-parse", "HEAD", cwd=source) == BASE
    assert run("git", "status", "--porcelain", cwd=source) == ""
    for relative, expected in BASE_HASHES.items():
        actual = hashlib.sha256((source / relative).read_bytes()).hexdigest()
        assert actual == expected, (relative, actual)
    numstat = run("git", "apply", "--numstat", str(PATCH), cwd=source)
    changed = {line.split("\t", 2)[2] for line in numstat.splitlines()}
    assert changed == PATHS, changed
    run("git", "apply", "--check", str(PATCH), cwd=source)
    assert run("git", "status", "--porcelain", cwd=source) == ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    static_contract()
    if args.source is not None:
        exact_source_check(args.source.resolve())
    print("PASS fa0 graph-cache port static contract")


if __name__ == "__main__":
    main()
