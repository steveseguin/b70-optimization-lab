#!/usr/bin/env python3
"""Direct-I/O model identity verifier.

Why this exists: on 2026-08-20 the measuring host's fuseblk/NTFS-3G page
cache served corrupted weight bytes through ordinary reads while
`dd iflag=direct` returned the correct bytes. Any verifier that hashes
through ordinary cached reads shares the page cache with the subsequent
safetensors/mmap load: both see the SAME bytes, so a cached-read verifier
cannot detect cache poisoning and will certify corrupted weights.

This verifier hashes every manifest entry bypassing the page cache:
  1. O_DIRECT preadv reads (page-aligned buffers), or
  2. `dd iflag=direct` streaming fallback when O_DIRECT is unavailable
     (some FUSE mounts), or
  3. FAIL CLOSED (exit 2) when neither works. A gate that cannot bypass
     the cache must not certify.

Usage:
  verify-model-direct.py MANIFEST_JSON MODEL_DIR [--json RESULT_JSON]

Exit codes: 0 all identities verified; 1 mismatch/missing; 2 cannot verify
bypassing the cache; 3 usage/config error.
"""
from __future__ import annotations

import hashlib
import json
import mmap
import os
import subprocess
import sys

DIRECT_BLOCK = 4096
CHUNK = DIRECT_BLOCK * 256  # 1 MiB aligned buffer


class DirectUnavailable(Exception):
    pass


def _open_direct(path: str) -> int:
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECT)
    except OSError as exc:
        raise DirectUnavailable(f"O_DIRECT open failed for {path}: {exc}")


def hash_direct(path: str, algorithm: str) -> str:
    """Hash a file with O_DIRECT reads; raises DirectUnavailable."""
    size = os.stat(path).st_size
    digest = hashlib.new(algorithm)
    fd = _open_direct(path)
    try:
        buf = mmap.mmap(-1, CHUNK)  # anonymous, page-aligned
        mv = memoryview(buf)
        off = 0
        while off < size:
            want = size - off
            req = ((min(want, CHUNK) + DIRECT_BLOCK - 1) // DIRECT_BLOCK) * DIRECT_BLOCK
            req = min(req, CHUNK)
            n = os.preadv(fd, [mv[:req]], off)
            if n <= 0:
                raise DirectUnavailable(
                    f"O_DIRECT read stalled at {off}/{size} on {path}"
                )
            digest.update(mv[:n])
            off += n
        return digest.hexdigest()
    except OSError as exc:
        raise DirectUnavailable(f"O_DIRECT read failed for {path}: {exc}")
    finally:
        os.close(fd)


def hash_dd(path: str, algorithm: str) -> str:
    """Stream through `dd iflag=direct`; raises DirectUnavailable."""
    digest = hashlib.new(algorithm)
    proc = subprocess.Popen(
        ["dd", f"if={path}", "iflag=direct", "bs=4M", "status=none"],
        stdout=subprocess.PIPE,
    )
    assert proc.stdout is not None
    for chunk in iter(lambda: proc.stdout.read(4 * 1024 * 1024), b""):
        digest.update(chunk)
    if proc.wait() != 0:
        raise DirectUnavailable(f"dd iflag=direct failed for {path}")
    return digest.hexdigest()


def hash_bypassing_cache(path: str, algorithm: str, mode: list[str]) -> str:
    """Hash with page-cache bypass; records which mode served."""
    try:
        mode.append("odirect")
        return hash_direct(path, algorithm)
    except DirectUnavailable:
        mode.pop()
    try:
        mode.append("dd")
        return hash_dd(path, algorithm)
    except (DirectUnavailable, FileNotFoundError):
        mode.pop()
    raise DirectUnavailable(
        f"cannot bypass page cache for {path}: O_DIRECT and dd iflag=direct "
        "both unavailable; drop caches (echo 3 > /proc/sys/vm/drop_caches) "
        "or remount the store, then re-verify"
    )


def read_bytes_bypassing_cache(path: str, mode: list[str]) -> bytes:
    size = os.stat(path).st_size
    fd = -1
    try:
        fd = _open_direct(path)
        buf = mmap.mmap(-1, ((max(size, 1) + DIRECT_BLOCK - 1) // DIRECT_BLOCK) * DIRECT_BLOCK)
        mv = memoryview(buf)
        off = 0
        while off < size:
            req = ((size - off + DIRECT_BLOCK - 1) // DIRECT_BLOCK) * DIRECT_BLOCK
            n = os.preadv(fd, [mv[:req]], off)
            if n <= 0:
                raise DirectUnavailable(f"O_DIRECT read stalled on {path}")
            off += n
        mode.append("odirect")
        return bytes(mv[:size])
    except (OSError, DirectUnavailable):
        if fd >= 0:
            os.close(fd)
            fd = -1
    if fd >= 0:
        os.close(fd)
    proc = subprocess.run(
        ["dd", f"if={path}", "iflag=direct", "bs=4M", "status=none"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise DirectUnavailable(f"cannot bypass page cache for {path}")
    mode.append("dd")
    return proc.stdout


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 3
    manifest_path, model_dir = sys.argv[1], sys.argv[2]
    json_out = None
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        json_out = sys.argv[i + 1]
    manifest = json.loads(open(manifest_path).read())

    modes: list[str] = []
    result = {"manifest": manifest_path, "model_dir": model_dir, "files": []}
    failures = []
    for section, algorithm, key in (
        ("lfs_files", "sha256", "sha256"),
        ("small_files", "sha1_git_blob", "git_blob"),
    ):
        for item in manifest.get(section, []):
            rel = item["path"]
            path = os.path.join(model_dir, rel)
            entry = {"path": rel, "section": section}
            if not os.path.isfile(path):
                entry["error"] = "missing"
                failures.append(entry)
                result["files"].append(entry)
                continue
            size = os.stat(path).st_size
            if size != item["bytes"]:
                entry["error"] = f"size {size} != manifest {item['bytes']}"
                failures.append(entry)
                result["files"].append(entry)
                continue
            try:
                if algorithm == "sha256":
                    actual = hash_bypassing_cache(path, "sha256", modes)
                else:
                    data = read_bytes_bypassing_cache(path, modes)
                    actual = hashlib.sha1(
                        b"blob " + str(len(data)).encode() + b"\0" + data
                    ).hexdigest()
            except DirectUnavailable as exc:
                entry["error"] = str(exc)
                result["files"].append(entry)
                print(f"CANNOT VERIFY: {rel}: {exc}", file=sys.stderr)
                if json_out:
                    result["status"] = "unverifiable"
                    json.dump(result, open(json_out, "w"), indent=1)
                return 2
            entry["actual"] = actual
            entry["expected"] = item[key]
            entry["ok"] = actual == item[key]
            if not entry["ok"]:
                failures.append(entry)
            result["files"].append(entry)
            print(("OK  " if entry["ok"] else "BAD"), rel, actual[:16], flush=True)

    result["read_modes"] = sorted(set(modes))
    result["status"] = "verified" if not failures else "mismatch"
    if json_out:
        json.dump(result, open(json_out, "w"), indent=1)
    if failures:
        print(f"IDENTITY MISMATCH on {len(failures)} file(s)", file=sys.stderr)
        return 1
    print(
        f"model revision and all recorded file identities verified "
        f"(page-cache bypass: {','.join(result['read_modes'])})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
