#!/usr/bin/env python3
"""Create the A46 worker-consumed-trace packet from standalone A45."""

from __future__ import annotations

import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
A45_DERIVED = "0e23faf443d746fcbbe94b66747115b8c4dd28f53d31ee6a7540573fd97a0282"
A46_DERIVED = "6fc3f7b87c85138247be89e86eb1602d6911b98be022d3fa752a9e327bec1d4f"
A43_VERIFIER = "verify-q38-a43-fullgraph-runtime.py"
A46_VERIFIER = "verify-q38-a46-fullgraph-runtime.py"
A43_VERIFIER_SHA256 = "c7748c0316de5cddf3366c28bea419294d51cad92ad14bad893d4c8234099888"
A46_VERIFIER_SHA256 = "724528810e5316e1a32c013ecc6a2d0419f7063a7cedf6c5cb7d05d4ea672310"


def replace_exact(text: str, old: str, new: str, count: int, label: str) -> str:
    actual = text.count(old)
    if actual != count:
        raise RewriteError(f"{label}: expected {count}, found {actual}")
    return text.replace(old, new)


def protect_digests(text: str) -> tuple[str, list[str]]:
    digests: list[str] = []

    def protect(match: re.Match[str]) -> str:
        digests.append(match.group(0))
        return f"Q38DIGESTTOKEN{len(digests) - 1}END"

    return HEX.sub(protect, text), digests


def restore_digests(text: str, digests: list[str]) -> str:
    for index, digest in enumerate(digests):
        marker = f"Q38DIGESTTOKEN{index}END"
        if text.count(marker) != 1:
            raise RewriteError(f"digest marker {index} drift")
        text = text.replace(marker, digest)
    return text


def common(text: str, mode: str) -> str:
    counts = {
        "launcher": {"attempt45": 1, "a45": 3, "A45": 6, "19717": 1},
        "client": {"attempt45": 3, "a45": 5, "A45": 1, "19717": 2},
        "supervisor": {"attempt45": 4, "a45": 4, "A45": 0, "19717": 1},
    }[mode]
    text, digests = protect_digests(text)
    for old, new, label in (
        ("attempt45", "attempt46", "attempt paths"),
        ("a45", "a46", "lower identity"),
        ("A45", "A46", "upper identity"),
        ("19717", "19718", "port"),
    ):
        text = replace_exact(text, old, new, counts[old], label)
    return restore_digests(text, digests)


def launcher(text: str) -> str:
    text = common(text, "launcher")
    text = replace_exact(text, "ATTEMPT=45", "ATTEMPT=46", 1, "inner attempt")
    return replace_exact(text, A45_DERIVED, A46_DERIVED, 1, "derived hash")


def client(text: str) -> str:
    text = common(text, "client")
    text = replace_exact(text, A43_VERIFIER, A46_VERIFIER, 1, "verifier path")
    return replace_exact(
        text,
        A43_VERIFIER_SHA256,
        A46_VERIFIER_SHA256,
        1,
        "verifier hash",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common(text, "supervisor")
    text = replace_exact(
        text,
        "952a339c02496f90a2cb1cb48caa1a548ffed4194a705d1925b014ab49eda8d6",
        wrapper_hash,
        1,
        "wrapper hash",
    )
    return replace_exact(
        text,
        "2646653e25e07dba4b846317902ba1eda3570b019d9cf2ff10534e37b64cf67f",
        client_hash,
        1,
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--wrapper-hash", default="A46_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A46_CLIENT_HASH")
    args = parser.parse_args()
    source = sys.stdin.read()
    if args.mode == "launcher":
        result = launcher(source)
    elif args.mode == "client":
        result = client(source)
    else:
        result = supervisor(source, args.wrapper_hash, args.client_hash)
    sys.stdout.write(result)


if __name__ == "__main__":
    main()
