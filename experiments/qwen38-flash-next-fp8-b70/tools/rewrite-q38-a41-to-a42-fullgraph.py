#!/usr/bin/env python3
"""Derive A42 with protected digests and the corrected trace receipt."""

from __future__ import annotations

import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt41": 0, "a41": 3, "A41": 6, "19713": 1, "libccl": 3},
    "client": {"attempt41": 3, "a41": 5, "A41": 1, "19713": 2, "libccl": 3},
    "supervisor": {"attempt41": 4, "a41": 4, "A41": 0, "19713": 1, "libccl": 2},
}
CORRECT_LIBCCL_DIGEST = (
    "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
)
OLD_DIAGNOSTIC_RECEIPT = "'diagnostics=full-decode-graph-public-oneccl' \\\n"
NEW_DIAGNOSTIC_RECEIPT = (
    "'diagnostics=full-decode-graph-public-oneccl-torch-trace' \\\n"
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
    expected = EXPECTED_COUNTS[mode]["libccl"]
    actual = text.count(CORRECT_LIBCCL_DIGEST)
    if actual != expected:
        raise RewriteError(f"libccl digest: expected {expected}, found {actual}")
    contaminated = sorted(
        digest for digest in HEX_DIGEST.findall(text) if "a42" in digest
    )
    if contaminated:
        raise RewriteError(f"attempt identity leaked into digests: {contaminated}")
    return text


def common_identity(text: str, mode: str) -> str:
    counts = EXPECTED_COUNTS[mode]
    text = replace_count(
        text, "attempt41", "attempt42", counts["attempt41"], "attempt paths"
    )
    text = replace_count(text, "a41", "a42", counts["a41"], "lowercase identity")
    text = replace_count(text, "A41", "A42", counts["A41"], "uppercase identity")
    return replace_count(text, "19713", "19714", counts["19713"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=7848b38ba6a57be8cd9ad86e1d624b0ab1f1e0a0ecde984e54588aa7eeae4757",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )
    text = replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=41 PORT=19714",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=42 PORT=19714",
        "inner launch attempt",
    )
    return audit_protected_digests(text, "launcher")


def client(text: str) -> str:
    text = common_identity(text, "client")
    text = replace_once(
        text,
        OLD_DIAGNOSTIC_RECEIPT,
        NEW_DIAGNOSTIC_RECEIPT,
        "trace diagnostic receipt",
    )
    return audit_protected_digests(text, "client")


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=0a3a77dc1f43ca7ed2ff3299c7b51165c68d708417489483518ddc9be636eb89",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    text = replace_once(
        text,
        "expected_client=bade97f7ec8bdc9bf969d6ffb0923882bbeb71620ea43766261a33558d7e802f",
        f"expected_client={client_hash}",
        "client hash",
    )
    return audit_protected_digests(text, "supervisor")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A42_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A42_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A42_CLIENT_HASH")
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
