#!/usr/bin/env python3
"""Derive A41 while protecting authority hashes from identity rewrites."""

from __future__ import annotations

import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt40": 0, "a40": 3, "A40": 6, "19712": 1, "libccl": 3},
    "client": {"attempt40": 3, "a40": 6, "A40": 1, "19712": 2, "libccl": 3},
    "supervisor": {"attempt40": 4, "a40": 4, "A40": 0, "19712": 1, "libccl": 2},
}
CORRUPTED_A41_PAYLOAD_DIGEST = (
    "2d92a2857d5cf45c3dcbc9d856cba714e2a41003295159fb5fcf1a8effb930be"
)
CORRECT_PAYLOAD_DIGEST = (
    "2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be"
)
CORRECT_LIBCCL_DIGEST = (
    "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
)
HEX_DIGEST = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RewriteError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    return replace_count(text, old, new, 1, label)


def audit_protected_digests(text: str, mode: str) -> str:
    expected_libccl = EXPECTED_COUNTS[mode]["libccl"]
    actual_libccl = text.count(CORRECT_LIBCCL_DIGEST)
    if actual_libccl != expected_libccl:
        raise RewriteError(
            f"protected libccl digest: expected {expected_libccl}, found {actual_libccl}"
        )
    contaminated = sorted(
        digest for digest in HEX_DIGEST.findall(text) if "a41" in digest
    )
    if contaminated:
        raise RewriteError(f"attempt identity leaked into digests: {contaminated}")
    return text


def common_identity(text: str, mode: str) -> str:
    counts = EXPECTED_COUNTS[mode]
    text = replace_count(
        text, "attempt40", "attempt41", counts["attempt40"], "attempt paths"
    )
    text = replace_count(text, "a40", "a41", counts["a40"], "lowercase identity")
    text = replace_count(text, "A40", "A41", counts["A40"], "uppercase identity")
    return replace_count(text, "19712", "19713", counts["19712"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=3b8c3833177b586a478945ef63851443e8971eb5858cac327ca5258b178b14e1",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )
    text = replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=40 PORT=19713",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=41 PORT=19713",
        "inner launch attempt",
    )
    return audit_protected_digests(text, "launcher")


def client(text: str) -> str:
    text = common_identity(text, "client")
    text = replace_once(
        text,
        CORRUPTED_A41_PAYLOAD_DIGEST,
        CORRECT_PAYLOAD_DIGEST,
        "protected exact-depth payload digest",
    )
    return audit_protected_digests(text, "client")


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=7f4452a9c62c9a49da68a416965280c697f9908942765e9da1a7afdcd2bd8bdb",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    text = replace_once(
        text,
        "expected_client=415d203f2752ddfccfe1963efd17cfd0483565fab592172b6c6ab5f323aa202d",
        f"expected_client={client_hash}",
        "client hash",
    )
    return audit_protected_digests(text, "supervisor")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A41_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A41_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A41_CLIENT_HASH")
    args = parser.parse_args()
    text = sys.stdin.read()
    if args.mode == "launcher":
        output = launcher(text, args.derived_hash)
    elif args.mode == "client":
        output = client(text)
    else:
        output = supervisor(text, args.wrapper_hash, args.client_hash)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
