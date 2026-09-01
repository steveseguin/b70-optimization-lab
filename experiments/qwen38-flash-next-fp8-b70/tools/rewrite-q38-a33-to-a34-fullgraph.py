#!/usr/bin/env python3
"""Derive A34 from A33 with fresh paths and a corrected runtime verifier."""

from __future__ import annotations

import argparse
import sys


class RewriteError(RuntimeError):
    pass


EXPECTED_COUNTS = {
    "launcher": {"attempt33": 0, "a33": 3, "A33": 6, "19705": 1},
    "client": {"attempt33": 3, "a33": 6, "A33": 1, "19705": 2},
    "supervisor": {"attempt33": 4, "a33": 4, "A33": 0, "19705": 1},
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
        text, "attempt33", "attempt34", counts["attempt33"], "attempt paths"
    )
    text = replace_count(text, "a33", "a34", counts["a33"], "lowercase identity")
    text = replace_count(text, "A33", "A34", counts["A33"], "uppercase identity")
    return replace_count(text, "19705", "19706", counts["19705"], "port identity")


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text, "launcher")
    text = replace_once(
        text,
        "expected_derived=fd25c815e4acb95fdc08d5aed050885dcda072bf9028931a86ce89e4194acad0",
        f"expected_derived={derived_hash}",
        "derived hash",
    )
    return replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=33 PORT=19706",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=34 PORT=19706",
        "launcher attempt",
    )


def client(text: str, runtime_verifier_hash: str) -> str:
    text = common_identity(text, "client")
    return replace_once(
        text,
        "expected_runtime_verifier=239f80b93531762ee607b2b651b3c69d4ba3d7b888c783ef989d321e7d834fae",
        f"expected_runtime_verifier={runtime_verifier_hash}",
        "runtime verifier hash",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text, "supervisor")
    text = replace_once(
        text,
        "expected_wrapper=776f608eee77fb8ad4b5d02496e9e68fa4e16392639e0fa471c857de5fffe02e",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    return replace_once(
        text,
        "expected_client=034b08e0eea247c98715646e2211c1507c4b435a06e5ba94703e12784d4e5ce1",
        f"expected_client={client_hash}",
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A34_DERIVED_HASH")
    parser.add_argument("--runtime-verifier-hash", default="A34_VERIFIER_HASH")
    parser.add_argument("--wrapper-hash", default="A34_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A34_CLIENT_HASH")
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
