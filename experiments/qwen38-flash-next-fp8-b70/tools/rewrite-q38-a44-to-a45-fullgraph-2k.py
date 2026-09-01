#!/usr/bin/env python3
"""Create the standalone A45 2K packet from flattened A44 sources."""

from __future__ import annotations

import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
A44_DERIVED = "35bd4afbc39cc05b1086407b22cdd840ff561b67c7a4ea44379aecc666bdc40d"
A45_DERIVED = "0e23faf443d746fcbbe94b66747115b8c4dd28f53d31ee6a7540573fd97a0282"


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
        "launcher": {"attempt44": 0, "a44": 3, "A44": 6, "19716": 1},
        "client": {"attempt44": 3, "a44": 5, "A44": 1, "19716": 2},
        "supervisor": {"attempt44": 4, "a44": 4, "A44": 0, "19716": 1},
    }[mode]
    text, digests = protect_digests(text)
    for old, new, label in (
        ("attempt44", "attempt45", "attempt paths"),
        ("a44", "a45", "lower identity"),
        ("A44", "A45", "upper identity"),
        ("19716", "19717", "port"),
    ):
        text = replace_exact(text, old, new, counts[old], label)
    return restore_digests(text, digests)


def launcher(text: str) -> str:
    text = common(text, "launcher")
    text = replace_exact(text, A44_DERIVED, A45_DERIVED, 1, "derived hash")
    text = replace_exact(text, "4352", "2304", 5, "launcher context")
    text = replace_exact(text, "ple4k", "ple2k", 3, "launcher path class")
    text = replace_exact(text, "ATTEMPT=44", "ATTEMPT=45", 1, "inner attempt")
    anchor = (
        "export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70\n"
    )
    trace = (
        anchor + "export TORCH_TRACE=${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-"
        "fullgraph-mtp0-2304-ple-only-r1-attempt45/torch-trace\n"
    )
    return replace_exact(text, anchor, trace, 1, "trace export")


def client(text: str) -> str:
    text = common(text, "client")
    for old, new, count, label in (
        ("4352", "2304", 10, "client context"),
        ("4372", "2157", 1, "needle filler"),
        ("4096", "2048", 4, "exact depth"),
        ("4224", "2176", 2, "capacity and exact total"),
        ("4K", "2K", 5, "upper depth label"),
        ("4k", "2k", 13, "lower depth label"),
        (
            "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0",
            "a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba",
            1,
            "prompt authority",
        ),
        (
            "2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be",
            "3aa1bba4d0ade3c07e7cad10bb5ee01245dc194d28dc17359311ece3b4ab6f36",
            1,
            "payload authority",
        ),
        (
            "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc",
            "5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e",
            1,
            "output authority",
        ),
    ):
        text = replace_exact(text, old, new, count, label)
    return text


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common(text, "supervisor")
    source_hash_pairs = (
        (
            "981d50ff49bcd605ce6c0792fffc64c5e72b1a3700c2bbcda240d85635056c6b",
            "431ebd4547150668610b9ed0d46574725202a279eedf7412b3d51c7ea1ce2904",
        ),
        (
            "bd33da88336112eb839c226a683948f2affbd6b478844bff6984dcb95a5716a0",
            "d42250a218197784cf28a7dec10140e23ce2f910a4fa88662c32bdf1d7b53425",
        ),
    )
    matches = [
        pair
        for pair in source_hash_pairs
        if text.count(pair[0]) == 1 and text.count(pair[1]) == 1
    ]
    if len(matches) != 1:
        raise RewriteError("supervisor source hash identity is ambiguous or absent")
    old_wrapper_hash, old_client_hash = matches[0]
    text = replace_exact(text, old_wrapper_hash, wrapper_hash, 1, "wrapper hash")
    text = replace_exact(text, old_client_hash, client_hash, 1, "client hash")
    for old, new, count, label in (
        ("4352", "2304", 8, "supervisor context"),
        ("4K", "2K", 3, "upper depth label"),
        ("4k", "2k", 5, "lower depth label"),
        (
            "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc",
            "5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e",
            1,
            "output authority",
        ),
    ):
        text = replace_exact(text, old, new, count, label)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--wrapper-hash", default="A45_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A45_CLIENT_HASH")
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
