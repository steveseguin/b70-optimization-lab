#!/usr/bin/env python3
"""Derive the path-corrected A38 successor from frozen A37 sources."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt37": 0, "a37": 6, "A37": 6, "19709": 1},
    "client": {"attempt37": 3, "a37": 10, "A37": 1, "19709": 2},
    "supervisor": {"attempt37": 4, "a37": 6, "A37": 0, "19709": 1},
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
        text, "attempt37", "attempt38", counts["attempt37"], "attempt paths"
    )
    text = replace_count(text, "a37", "a38", counts["a37"], "lowercase identity")
    text = replace_count(text, "A37", "A38", counts["A37"], "uppercase identity")
    return replace_count(text, "19709", "19710", counts["19709"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=eb3d3995be5a4bd433f95733124e63d1a57e24a83a35461a33e9ce667f280014",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=36 PORT=19710",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=38 PORT=19710",
        "inner launch attempt",
    )


def client(text: str) -> str:
    text = common_identity(text, "client")
    return replace_once(
        text,
        "verify-q38-a38-fullgraph-runtime.py",
        "verify-q38-a37-fullgraph-runtime.py",
        "reuse audited A37 verifier",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=4770b437848c5ed913d9ce74055b91dab0e7eaa3845e9b9ac42ea2777bc508a7",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=eb1e81820de1766b8e577dd3296bb800dcbfd7ca60d7e75f33e8ee3dda15bd1c",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A38_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A38_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A38_CLIENT_HASH")
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
