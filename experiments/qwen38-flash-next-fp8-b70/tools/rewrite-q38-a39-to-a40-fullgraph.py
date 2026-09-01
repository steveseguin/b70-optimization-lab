#!/usr/bin/env python3
"""Derive A40 while protecting checksum literals from identity rewrites."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt39": 0, "a39": 6, "A39": 6, "19711": 1, "digest": 3},
    "client": {"attempt39": 3, "a39": 9, "A39": 1, "19711": 2, "digest": 3},
    "supervisor": {"attempt39": 4, "a39": 6, "A39": 0, "19711": 1, "digest": 2},
}

CORRUPTED_A40_DIGEST = (
    "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a40fad6700"
)
CORRECT_LIBCCL_DIGEST = (
    "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
)


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
        text, "attempt39", "attempt40", counts["attempt39"], "attempt paths"
    )
    text = replace_count(text, "a39", "a40", counts["a39"], "lowercase identity")
    text = replace_count(text, "A39", "A40", counts["A39"], "uppercase identity")
    text = replace_count(text, "19711", "19712", counts["19711"], "port identity")
    return replace_count(
        text,
        CORRUPTED_A40_DIGEST,
        CORRECT_LIBCCL_DIGEST,
        counts["digest"],
        "protected libccl digest",
    )


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=761fad8e8f7d7c2977178b21053a5013f293e282656eb6cdf22365c3f8b195cd",
        f"expected_derived={derived_hash}",
        "inner derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=39 PORT=19712",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=40 PORT=19712",
        "inner launch attempt",
    )


def client(text: str) -> str:
    return common_identity(text, "client")


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=e3f88d5d4b898e50724ad6cd83986c571fdb7293c23788a26bb29fc50a7aa6f3",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=d7599824c4a31bf33e1de17e6f99312e3f7f98711f544716ed9614e99ab4dffb",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A40_DERIVED_HASH")
    parser.add_argument("--wrapper-hash", default="A40_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A40_CLIENT_HASH")
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
