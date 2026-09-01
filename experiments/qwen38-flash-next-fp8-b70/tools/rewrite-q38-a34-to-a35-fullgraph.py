#!/usr/bin/env python3
"""Derive the path-only A35 successor from the frozen A34 sources."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt34": 0, "a34": 3, "A34": 6, "19706": 1},
    "client": {"attempt34": 3, "a34": 6, "A34": 1, "19706": 2},
    "supervisor": {"attempt34": 4, "a34": 5, "A34": 0, "19706": 1},
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
        text, "attempt34", "attempt35", counts["attempt34"], "attempt paths"
    )
    text = replace_count(text, "a34", "a35", counts["a34"], "lowercase identity")
    text = replace_count(text, "A34", "A35", counts["A34"], "uppercase identity")
    return replace_count(text, "19706", "19707", counts["19706"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=ca84bb3d2a5d7792313c9ee1584b9da2dbe06bc32b148a4fa31c43fd224e2033",
        f"expected_derived={derived_hash}",
        "derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=34 PORT=19707",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=35 PORT=19707",
        "launcher attempt",
    )


def client(text: str) -> str:
    text = common_identity(text, "client")
    return replace_once(
        text,
        "verify-q38-a35-fullgraph-runtime.py",
        "verify-q38-a34-fullgraph-runtime.py",
        "frozen A34 verifier dependency",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=6a2629debf63dc63c759d6c6eea35897ff7a0cc17b709febb1a7078499151531",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=cf9b044839c5027f57bc74982328adf969c131921aba3b222704b269285da247",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A35_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A35_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A35_CLIENT_HASH")
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
