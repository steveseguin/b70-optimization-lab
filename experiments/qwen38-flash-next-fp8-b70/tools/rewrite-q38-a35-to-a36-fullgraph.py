#!/usr/bin/env python3
"""Derive A36 from A35 with fresh paths and the holistic runtime verifier."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt35": 0, "a35": 3, "A35": 6, "19707": 1},
    "client": {"attempt35": 3, "a35": 5, "A35": 1, "19707": 2},
    "supervisor": {"attempt35": 4, "a35": 4, "A35": 0, "19707": 1},
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
        text, "attempt35", "attempt36", counts["attempt35"], "attempt paths"
    )
    text = replace_count(text, "a35", "a36", counts["a35"], "lowercase identity")
    text = replace_count(text, "A35", "A36", counts["A35"], "uppercase identity")
    return replace_count(text, "19707", "19708", counts["19707"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=6a21d4a751ff40299e772917447884c822fcff193bee6e23276db51ee2e045ca",
        f"expected_derived={derived_hash}",
        "derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=35 PORT=19708",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=36 PORT=19708",
        "launcher attempt",
    )


def client(text: str, runtime_verifier_hash: str) -> str:
    text = common_identity(text, "client")
    text = replace_once(
        text,
        "verify-q38-a34-fullgraph-runtime.py",
        "verify-q38-a36-fullgraph-runtime.py",
        "A36 runtime verifier path",
    )
    return replace_once(
        text,
        "expected_runtime_verifier=679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747",
        f"expected_runtime_verifier={runtime_verifier_hash}",
        "A36 runtime verifier hash",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=8cea3b85a3aa332e46e35eacfdf2096e59a760343fb21d042f819442c4b8a11f",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=264c27d0fb014f6a7340f392b70df84e7250f04a71f91eab2570965ba4c10bf5",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A36_DERIVED_HASH")
    parser.add_argument("--runtime-verifier-hash", default="A36_VERIFIER_HASH")
    parser.add_argument("--wrapper-hash", default="A36_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A36_CLIENT_HASH")
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
