#!/usr/bin/env python3
"""Reconstruct and statically validate the fa0 graph-cache Q8 r2 patch chain."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PARENT_PATCH = REPO / "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-evidence-port-20260825.patch"
R2_PATCH = REPO / "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-q8-pointer-stable-r2-20260825.patch"
BASE = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
SYCL = Path("ggml/src/ggml-sycl/ggml-sycl.cpp")
COMMON = Path("ggml/src/ggml-sycl/common.hpp")

PATCH_HASHES = {
    PARENT_PATCH: "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892",
    R2_PATCH: "1575acc5ee07b37eb98186a09d201a895d36501c223dc114110a43ee08f4e0a3",
}
BASE_HASHES = {
    COMMON: "25e2323e6199c25b840c4c2f5729389963358faa892de1ee6b71a08619ac7be8",
    SYCL: "561a275ca5abfc437fdbf126a5d1b475755558d6cec9cac3f5f66d1af8c241bd",
}
AFTER_PARENT_HASHES = {
    COMMON: "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
    SYCL: "024fda2f9e667aa82cfdac64c079b5cb932e6a40e90031ad16cfd142bec93544",
}
AFTER_R2_HASHES = {
    COMMON: "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
    SYCL: "f0c4bda8beb3c0b06c72edc202fcc074d72e031433a4eacd8a91b8acf5f468a0",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def require_hashes(root: Path, expected: dict[Path, str]) -> None:
    for relative, wanted in expected.items():
        actual = sha256(root / relative)
        assert actual == wanted, (str(relative), actual, wanted)


def static_patch_contract() -> None:
    for patch, wanted in PATCH_HASHES.items():
        assert sha256(patch) == wanted, patch

    text = R2_PATCH.read_text(encoding="utf-8")
    headers = {
        line.removeprefix("+++ b/")
        for line in text.splitlines()
        if line.startswith("+++ b/")
    }
    assert headers == {str(SYCL)}, headers

    required = (
        "g_ggml_sycl_enable_graph != 0 && g_ggml_sycl_graph_cache_size > 0",
        "if (!preserve_graph_cache_pointers)",
        "retain the accepted graph-off first-stale policy",
        "if (e.cap >= size && (slot == nullptr || e.cap < slot->cap))",
        "else if (preserve_graph_cache_pointers)",
        "persistent SYCL graph Q8 memo exhausted",
        "persistent SYCL graph Q8 memo allocation failed",
        "GGML_ASSERT(!preserve_graph_cache_pointers)",
        "q->wait();",
        "slot = &ctx.q8_memo[ctx.q8_memo_cursor]",
        "sycl_ctx->stream()->wait_and_throw();",
        "sycl_ctx->graph_cache.clear();",
        "sycl_ctx->exec_graph.reset();",
    )
    for marker in required:
        assert marker in text, marker

    assert "GGML_SYCL_Q8_MEMO_SLOTS = 320" not in text

    # The graph-off/cache-zero policy must still select the first stale slot,
    # independent of its capacity. Best-fit is confined to persistent graphs.
    cases = (
        ([(0, 1), (0, 4096)], 1, 2048),
        ([(1, 64), (0, 4096), (0, 1)], 1, 2048),
        ([(2, 4096), (1, 1), (0, 64)], 2, 8192),
        ([(1, 1), (1, 64)], 1, 4096),
    )
    for entries, generation, requested in cases:
        old_slot = next((i for i, (entry_gen, _) in enumerate(entries) if entry_gen != generation), None)
        new_slot = None
        preserve = False
        for i, (entry_gen, capacity) in enumerate(entries):
            if entry_gen != generation:
                if not preserve:
                    new_slot = i
                    break
                if capacity >= requested and (new_slot is None or capacity < entries[new_slot][1]):
                    new_slot = i
        assert new_slot == old_slot


def reconstruct(source: Path) -> None:
    assert source.is_dir(), source
    assert run("git", "rev-parse", "HEAD", cwd=source) == BASE
    assert run("git", "status", "--porcelain", cwd=source) == ""
    require_hashes(source, BASE_HASHES)

    with tempfile.TemporaryDirectory(prefix="fa0-graph-q8-r2-static-") as raw:
        tree = Path(raw)
        for relative in BASE_HASHES:
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)

        run("git", "apply", "--check", str(PARENT_PATCH), cwd=tree)
        run("git", "apply", str(PARENT_PATCH), cwd=tree)
        require_hashes(tree, AFTER_PARENT_HASHES)

        run("git", "apply", "--check", str(R2_PATCH), cwd=tree)
        run("git", "apply", str(R2_PATCH), cwd=tree)
        require_hashes(tree, AFTER_R2_HASHES)

        final = (tree / SYCL).read_text(encoding="utf-8")
        assert final.count("const bool preserve_graph_cache_pointers =") == 1
        assert "if (!preserve_graph_cache_pointers) {" in final
        assert "if (e.cap >= size && (slot == nullptr || e.cap < slot->cap))" in final
        assert "else if (preserve_graph_cache_pointers)" in final
        assert "GGML_ASSERT(!preserve_graph_cache_pointers);" in final
        assert "sycl::free(slot->buf, *q);" in final
        teardown = final.index("sycl_ctx->stream()->wait_and_throw();")
        cache_clear = final.index("sycl_ctx->graph_cache.clear();", teardown)
        legacy_reset = final.index("sycl_ctx->exec_graph.reset();", cache_clear)
        context_delete = final.index("delete sycl_ctx;", legacy_reset)
        assert teardown < cache_clear < legacy_reset < context_delete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    static_patch_contract()
    reconstruct(args.source.resolve())
    print("PASS fa0 graph-cache Q8 pointer-stable r2 patch chain")


if __name__ == "__main__":
    main()
