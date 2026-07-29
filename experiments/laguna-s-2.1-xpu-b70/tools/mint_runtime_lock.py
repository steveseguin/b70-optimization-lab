#!/usr/bin/env python3
"""Mint a runtime lock for a newly built libgrouped_gemm_xe_2.so.

Copies the SEALED packet lock and changes exactly one field: the sha256 of the
mapped grouped-GEMM library. The sealed lock is never edited in place, and the
entry is located by path rather than by index so a reordering upstream cannot
silently rewrite the wrong library's hash.

usage: mint_runtime_lock.py <new.so> <output-lock.json>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SEALED = Path(
    "/home/steve/llm-optimizations/repro/"
    "laguna-s-2.1-int4-b70-102tps-20260726/manifests/runtime-lock.json"
)
LIBRARY = "libgrouped_gemm_xe_2.so"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(so_path: str, out_path: str) -> int:
    so, out = Path(so_path), Path(out_path)
    if not so.is_file():
        print(f"missing shared object: {so}", file=sys.stderr)
        return 2
    if out.resolve() == SEALED.resolve():
        print("refusing to overwrite the sealed lock", file=sys.stderr)
        return 2

    raw = SEALED.read_text()
    lock = json.loads(raw)

    # Faithfulness check: the sealed file must round-trip byte-for-byte under
    # our serializer, or "copy and change one field" is not what we are doing.
    if json.dumps(lock, indent=2) + "\n" != raw:
        print("sealed lock does not round-trip under this serializer", file=sys.stderr)
        return 2

    entries = [e for e in lock["mapped_kernel_libraries"] if e["path"] == LIBRARY]
    if len(entries) != 1:
        print(f"expected exactly one {LIBRARY} entry, found {len(entries)}", file=sys.stderr)
        return 2

    new_hash = sha256_file(so)
    old_hash = entries[0]["sha256"]
    entries[0]["sha256"] = new_hash

    out.write_text(json.dumps(lock, indent=2) + "\n")
    lock_hash = sha256_file(out)

    print(f"library    : {LIBRARY}")
    print(f"source     : {so}")
    print(f"sha256     : {old_hash} -> {new_hash}")
    print(f"lock       : {out}")
    print(f"lock sha256: {lock_hash}")
    print()
    print("export the leg environment with:")
    print(f"  REPRO_GROUPED_GEMM_SHA256={new_hash}")
    print(f"  REPRO_RUNTIME_LOCK={out}")
    print(f"  REPRO_RUNTIME_LOCK_SHA256={lock_hash}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
