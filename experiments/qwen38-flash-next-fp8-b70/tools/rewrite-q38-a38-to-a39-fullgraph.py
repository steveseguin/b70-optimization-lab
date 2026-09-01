#!/usr/bin/env python3
"""Derive fresh A39 paths from the frozen A38 source set."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt38": 0, "a38": 6, "A38": 6, "19710": 1},
    "client": {"attempt38": 3, "a38": 9, "A38": 1, "19710": 2},
    "supervisor": {"attempt38": 4, "a38": 6, "A38": 0, "19710": 1},
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
        text, "attempt38", "attempt39", counts["attempt38"], "attempt paths"
    )
    text = replace_count(text, "a38", "a39", counts["a38"], "lowercase identity")
    text = replace_count(text, "A38", "A39", counts["A38"], "uppercase identity")
    return replace_count(text, "19710", "19711", counts["19710"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=74413cb6784f47328b923fefd2a7fc523d943140eba2a5fca8161372e86c2c31",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=38 PORT=19711",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=39 PORT=19711",
        "inner launch attempt",
    )


def client(text: str) -> str:
    return common_identity(text, "client")


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=c4cf7f8e9a5edfd52f6624668503899ca0b60f52acc4ea93f4d153900f0a3915",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=33a43865033539c699f73ecabdfee41a9bb2ea17e5ad4ffdc0088678d02c5a81",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A39_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A39_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A39_CLIENT_HASH")
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
