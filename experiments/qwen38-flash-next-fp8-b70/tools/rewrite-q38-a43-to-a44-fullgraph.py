#!/usr/bin/env python3
"""Derive fresh A44 paths from the audited A43 source set."""

from __future__ import annotations
import argparse
import re
import sys


class RewriteError(RuntimeError):
    pass


COUNTS = {
    "launcher": {"attempt43": 0, "a43": 3, "A43": 6, "19715": 1, "libccl": 3},
    "client": {"attempt43": 3, "a43": 5, "A43": 1, "19715": 2, "libccl": 3},
    "supervisor": {"attempt43": 4, "a43": 4, "A43": 0, "19715": 1, "libccl": 2},
}
LIBCCL = "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
RUNTIME_VERIFIER = "verify-q38-a43-fullgraph-runtime.py"
HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def rep(t, o, n, c, label):
    a = t.count(o)
    if a != c:
        raise RewriteError(f"{label}: expected {c}, found {a}")
    return t.replace(o, n)


def common(t, m):
    c = COUNTS[m]
    t = rep(t, "attempt43", "attempt44", c["attempt43"], "paths")
    t = rep(t, "a43", "a44", c["a43"], "lower")
    t = rep(t, "A43", "A44", c["A43"], "upper")
    t = rep(t, "19715", "19716", c["19715"], "port")
    if t.count(LIBCCL) != c["libccl"]:
        raise RewriteError("libccl count drift")
    if any("a44" in d for d in HEX.findall(t)):
        raise RewriteError("identity leaked into digest")
    return t


def launcher(t, h):
    t = common(t, "launcher")
    t = rep(
        t,
        "expected_derived=4f4d4160b675d933e479621e20dbcb838c8549ba6c3a65779473da944f4e7b94",
        f"expected_derived={h}",
        1,
        "derived",
    )
    return rep(
        t,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=43 PORT=19716",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=44 PORT=19716",
        1,
        "inner attempt",
    )


def client(t):
    if t.count(RUNTIME_VERIFIER) != 1:
        raise RewriteError("runtime verifier identity drift")
    placeholder = "Q38_RUNTIME_VERIFIER_IDENTITY.py"
    t = t.replace(RUNTIME_VERIFIER, placeholder)
    t = common(t, "client")
    return t.replace(placeholder, RUNTIME_VERIFIER)


def supervisor(t, w, c):
    t = common(t, "supervisor")
    t = rep(
        t,
        "expected_wrapper=f61eb6bd3bc92c64d938d24c0038bf06f543ab89f60104dc34b8d9286b97118b",
        f"expected_wrapper={w}",
        1,
        "wrapper",
    )
    return rep(
        t,
        "expected_client=2fc3d2e1ddfb8428a90aee45a8b7889011c1275737a507d4cbe3f1fc96019a73",
        f"expected_client={c}",
        1,
        "client",
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("launcher", "client", "supervisor"))
    p.add_argument("--derived-hash", default="A44_DERIVED_HASH")
    p.add_argument("--wrapper-hash", default="A44_WRAPPER_HASH")
    p.add_argument("--client-hash", default="A44_CLIENT_HASH")
    a = p.parse_args()
    t = sys.stdin.read()
    sys.stdout.write(
        launcher(t, a.derived_hash)
        if a.mode == "launcher"
        else client(t)
        if a.mode == "client"
        else supervisor(t, a.wrapper_hash, a.client_hash)
    )


if __name__ == "__main__":
    main()
