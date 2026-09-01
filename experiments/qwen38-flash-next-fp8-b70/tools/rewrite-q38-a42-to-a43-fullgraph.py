#!/usr/bin/env python3
"""Derive A43 with the EngineCore-aware trace verifier."""

from __future__ import annotations

import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


COUNTS = {
    "launcher": {"attempt42": 0, "a42": 3, "A42": 6, "19714": 1, "libccl": 3},
    "client": {"attempt42": 3, "a42": 5, "A42": 1, "19714": 2, "libccl": 3},
    "supervisor": {"attempt42": 4, "a42": 4, "A42": 0, "19714": 1, "libccl": 2},
}
LIBCCL = "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def replace(text: str, old: str, new: str, count: int, label: str) -> str:
    actual = text.count(old)
    if actual != count:
        raise RewriteError(f"{label}: expected {count}, found {actual}")
    return text.replace(old, new)


def common(text: str, mode: str) -> str:
    counts = COUNTS[mode]
    text = replace(text, "attempt42", "attempt43", counts["attempt42"], "paths")
    text = replace(text, "a42", "a43", counts["a42"], "lower identity")
    text = replace(text, "A42", "A43", counts["A42"], "upper identity")
    text = replace(text, "19714", "19715", counts["19714"], "port")
    if text.count(LIBCCL) != counts["libccl"]:
        raise RewriteError("libccl digest count drift")
    contaminated = [digest for digest in HEX.findall(text) if "a43" in digest]
    if contaminated:
        raise RewriteError(f"attempt identity leaked into digests: {contaminated}")
    return text


def launcher(text: str, derived_hash: str) -> str:
    text = common(text, "launcher")
    text = replace(
        text,
        "expected_derived=b9ee60b7cf602eb207c7036eadf879e98e311e52d3d67cf77492559ed96065aa",
        f"expected_derived={derived_hash}",
        1,
        "derived hash",
    )
    return replace(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=42 PORT=19715",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=43 PORT=19715",
        1,
        "inner attempt",
    )


def client(text: str, verifier_hash: str) -> str:
    text = common(text, "client")
    text = replace(
        text,
        "verify-q38-a37-fullgraph-runtime.py",
        "verify-q38-a43-fullgraph-runtime.py",
        1,
        "verifier path",
    )
    return replace(
        text,
        "expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a",
        f"expected_runtime_verifier={verifier_hash}",
        1,
        "verifier hash",
    )


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common(text, "supervisor")
    text = replace(
        text,
        "expected_wrapper=62f584a1dccb04f5135208b875a1c1813362f4307b3b007b629f3be7a19f340d",
        f"expected_wrapper={wrapper_hash}",
        1,
        "wrapper hash",
    )
    return replace(
        text,
        "expected_client=0d179506dfa6a9c8f66106932b327cfc12bf3f2d0af7267a9429acd626fc72ad",
        f"expected_client={client_hash}",
        1,
        "client hash",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A43_DERIVED_HASH")
    parser.add_argument("--verifier-hash", default="A43_VERIFIER_HASH")
    parser.add_argument("--wrapper-hash", default="A43_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A43_CLIENT_HASH")
    args = parser.parse_args()
    text = sys.stdin.read()
    if args.mode == "launcher":
        output = launcher(text, args.derived_hash)
    elif args.mode == "client":
        output = client(text, args.verifier_hash)
    else:
        output = supervisor(text, args.wrapper_hash, args.client_hash)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
