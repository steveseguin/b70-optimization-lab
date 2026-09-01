#!/usr/bin/env python3
"""Derive A37 from A36 with fresh paths and the cache-aware verifier."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt36": 0, "a36": 3, "A36": 6, "19708": 1},
    "client": {"attempt36": 3, "a36": 7, "A36": 1, "19708": 2},
    "supervisor": {"attempt36": 4, "a36": 4, "A36": 0, "19708": 1},
}


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RewriteError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    return replace_count(text, old, new, 1, label)


def common_identity(text: str, mode: str) -> str:
    counts = EXPECTED_COUNTS[mode]
    text = replace_count(
        text, "attempt36", "attempt37", counts["attempt36"], "attempt paths"
    )
    text = replace_count(text, "a36", "a37", counts["a36"], "lowercase identity")
    text = replace_count(text, "A36", "A37", counts["A36"], "uppercase identity")
    return replace_count(text, "19708", "19709", counts["19708"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_count(
        text,
        "full-decode-graph-public-oneccl",
        "full-decode-graph-public-oneccl-torch-trace",
        3,
        "trace diagnostic identity",
    )
    return replace_once(
        text,
        "expected_derived=770fd21fab94a38481b2cf0c9372539e911eab6b07c38e968586655fd6f70f9b",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )


def client(text: str, runtime_verifier_hash: str) -> str:
    text = common_identity(text, "client")
    text = replace_once(
        text,
        "expected_runtime_verifier=256de72996103f284635c7402ceaa3d41ac8af877aabe773a1af10a84f09ae16",
        f"expected_runtime_verifier={runtime_verifier_hash}",
        "A37 runtime verifier hash",
    )
    text = replace_once(
        text,
        "torchinductor_cache=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt37-compile/torchinductor",
        "torchinductor_cache=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt37-compile/torchinductor\n"
        "torch_trace=${run_dir}/torch-trace",
        "Torch trace path",
    )
    text = replace_count(
        text,
        '--torchinductor-cache "$torchinductor_cache" --phase',
        '--torchinductor-cache "$torchinductor_cache" --torch-trace "$torch_trace" --phase',
        2,
        "Torch trace verifier arguments",
    )
    text = replace_once(
        text,
        '"diagnostics": "full-decode-graph-public-oneccl",',
        '"diagnostics": "full-decode-graph-public-oneccl-torch-trace",\n'
        '        "torch_trace_policy": "dynamo-exact-target-allowlist-v1",',
        "summary diagnostic identity",
    )
    return replace_once(
        text,
        ".torchinductor_files == []",
        '.schema_version == 2 and .compilation_mode == "NONE" and\n'
        "  .inductor_disabled_receipts > 0 and\n"
        '  .torchinductor_cache.interpretation == "trace_attributed_nested_operator_cache" and\n'
        "  .torchinductor_cache.file_count > 0 and\n"
        "  .torch_trace.compile_event_count > 0",
        "client cache and trace receipt",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=ce86f0f784b505d7ce123cc4f38a7ccb0cb812cc17387ed87ceb8f0fd6145286",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    text = replace_once(
        text,
        "expected_client=1949bbc71a62847525156d05f73851a3c9b4dab058bc7b4931e2a3dba8604b5f",
        f"expected_client={client_hash}",
        "client hash",
    )
    text = replace_once(
        text,
        '.identity.diagnostics == "full-decode-graph-public-oneccl" and',
        '.identity.diagnostics == "full-decode-graph-public-oneccl-torch-trace" and\n'
        '         .identity.torch_trace_policy == "dynamo-exact-target-allowlist-v1" and',
        "supervisor diagnostic identity",
    )
    return replace_once(
        text,
        ".torchinductor_files == []",
        '.schema_version == 2 and .compilation_mode == "NONE" and\n'
        "         .inductor_disabled_receipts > 0 and\n"
        '         .torchinductor_cache.interpretation == "trace_attributed_nested_operator_cache" and\n'
        "         .torchinductor_cache.file_count > 0 and\n"
        "         .torch_trace.compile_event_count > 0",
        "supervisor cache and trace receipt",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A37_DERIVED_HASH")
    parser.add_argument("--runtime-verifier-hash", default="A37_VERIFIER_HASH")
    parser.add_argument("--wrapper-hash", default="A37_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A37_CLIENT_HASH")
    args = parser.parse_args()
    text = sys.stdin.read()
    if args.mode == "launcher":
        output = launcher(text, args.derived_hash)
    elif args.mode == "client":
        output = client(text, args.runtime_verifier_hash)
    else:
        output = supervisor(text, args.wrapper_hash, args.client_hash)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
