#!/usr/bin/env python3
"""Direct-and-ordinary model identity verifier.

Why this exists: on 2026-08-20 the measuring host's fuseblk/NTFS-3G page
cache served corrupted weight bytes through ordinary reads while
`dd iflag=direct` returned the correct bytes. Any verifier that hashes
through ordinary cached reads shares the page cache with the subsequent
safetensors/mmap load: both see the SAME bytes, so a cached-read verifier
cannot detect cache poisoning and will certify corrupted weights.

This verifier hashes every manifest entry twice immediately before launch:
  1. O_DIRECT preadv reads (page-aligned buffers), or
  2. `dd iflag=direct` streaming fallback when O_DIRECT is unavailable
     (some FUSE mounts), or
  3. FAIL CLOSED (exit 2) when neither direct mode works; and
  4. an ordinary buffered read, matching the cache path used by the later
     safetensors/mmap load.

Both digests must match the manifest and each other. Direct-only verification
can prove that backing-store bytes are correct while still certifying poisoned
page-cache bytes, which is the exact failure mode this gate must reject.

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
import re
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
    buf = None
    mv = None
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
        if mv is not None:
            mv.release()
        if buf is not None:
            buf.close()
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


def hash_ordinary(path: str, algorithm: str) -> str:
    """Hash through the normal page-cache path used by the model loader."""
    digest = hashlib.new(algorithm)
    with open(path, "rb", buffering=0) as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bytes_bypassing_cache(path: str, mode: list[str]) -> bytes:
    size = os.stat(path).st_size
    fd = -1
    buf = None
    mv = None
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
        pass
    finally:
        if mv is not None:
            mv.release()
        if buf is not None:
            buf.close()
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


def git_blob_digest(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest()


def write_result(path: str, result: dict) -> None:
    with open(path, "w") as destination:
        json.dump(result, destination, indent=1)


def validate_manifest(manifest: object) -> list[str]:
    """Reject schemas that could turn a zero-work check into success."""
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    for field in ("repository", "revision"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"{field} must be a non-empty string")
    seen = set()
    total = 0
    for section, digest_key, digest_pattern in (
        ("lfs_files", "sha256", r"[0-9a-f]{64}"),
        ("small_files", "git_blob", r"[0-9a-f]{40}"),
    ):
        items = manifest.get(section)
        if not isinstance(items, list):
            errors.append(f"{section} must be a list")
            continue
        if section == "lfs_files" and not items:
            errors.append("lfs_files must contain at least one weight file")
        for index, item in enumerate(items):
            label = f"{section}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            rel = item.get("path")
            if (
                not isinstance(rel, str)
                or not rel
                or os.path.isabs(rel)
                or "\0" in rel
                or "\\" in rel
                or os.path.normpath(rel) != rel
                or rel == ".."
                or rel.startswith("../")
            ):
                errors.append(
                    f"{label}.path must be a normalized safe relative path"
                )
            elif rel in seen:
                errors.append(f"duplicate manifest path: {rel}")
            else:
                seen.add(rel)
            size = item.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                errors.append(f"{label}.bytes must be a positive integer")
            digest = item.get(digest_key)
            if (
                not isinstance(digest, str)
                or re.fullmatch(digest_pattern, digest) is None
            ):
                errors.append(f"{label}.{digest_key} has an invalid digest")
            total += 1
    if total == 0:
        errors.append("manifest contains no file entries")
    return errors


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 3
    manifest_path, model_dir = sys.argv[1], sys.argv[2]
    json_out = None
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        if i + 1 >= len(sys.argv):
            print("--json requires a result path", file=sys.stderr)
            return 3
        json_out = sys.argv[i + 1]
    try:
        with open(manifest_path) as source:
            manifest = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid manifest: {exc}", file=sys.stderr)
        if json_out:
            write_result(json_out, {
                "manifest": manifest_path,
                "model_dir": model_dir,
                "status": "config-error",
                "errors": [str(exc)],
            })
        return 3

    modes: list[str] = []
    result = {
        "manifest": manifest_path,
        "model_dir": model_dir,
        "verification": "direct-and-ordinary",
        "files": [],
    }
    schema_errors = validate_manifest(manifest)
    if schema_errors:
        result["status"] = "config-error"
        result["errors"] = schema_errors
        for error in schema_errors:
            print(f"invalid manifest: {error}", file=sys.stderr)
        if json_out:
            write_result(json_out, result)
        return 3
    failures = []
    work_items = []

    # Pass one: validate file metadata and hash every backing-store view. Do
    # not interleave ordinary reads here: the complete ordinary pass must be
    # the last model-data operation before the caller launches vLLM.
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
            entry["expected"] = item[key]
            result["files"].append(entry)
            work_items.append((entry, path, algorithm))
            try:
                if algorithm == "sha256":
                    direct_actual = hash_bypassing_cache(
                        path, "sha256", modes
                    )
                else:
                    direct_data = read_bytes_bypassing_cache(path, modes)
                    direct_actual = git_blob_digest(direct_data)
            except DirectUnavailable as exc:
                entry["error"] = str(exc)
                print(f"CANNOT VERIFY: {rel}: {exc}", file=sys.stderr)
                result["read_modes"] = sorted(set(modes))
                result["status"] = "unverifiable"
                if json_out:
                    write_result(json_out, result)
                return 2
            entry["direct_actual"] = direct_actual
            entry["direct_mode"] = modes[-1]
            entry["direct_ok"] = direct_actual == entry["expected"]

    # Pass two: hash the ordinary page-cache view for every file. This pass is
    # intentionally complete and last, so it certifies the bytes the imminent
    # safetensors/mmap load is expected to observe.
    for entry, path, algorithm in work_items:
        try:
            if algorithm == "sha256":
                ordinary_actual = hash_ordinary(path, "sha256")
            else:
                with open(path, "rb") as source:
                    ordinary_actual = git_blob_digest(source.read())
        except OSError as exc:
            entry["error"] = f"ordinary read failed: {exc}"
            failures.append(entry)
            print(f"CANNOT VERIFY: {entry['path']}: {exc}", file=sys.stderr)
            continue
        entry["ordinary_actual"] = ordinary_actual
        entry["ordinary_ok"] = ordinary_actual == entry["expected"]
        if "direct_actual" in entry:
            entry["paths_coherent"] = (
                entry["direct_actual"] == ordinary_actual
            )
        else:
            entry["paths_coherent"] = False
        entry["ok"] = (
            entry.get("direct_ok", False)
            and entry["ordinary_ok"]
            and entry["paths_coherent"]
        )
        if not entry["ok"]:
            failures.append(entry)
        print(
            ("OK  " if entry["ok"] else "BAD"),
            entry["path"],
            f"direct={entry.get('direct_actual', '')[:16]}",
            f"ordinary={ordinary_actual[:16]}",
            flush=True,
        )

    result["read_modes"] = sorted(set(modes))
    result["status"] = "verified" if not failures else "mismatch"
    if json_out:
        write_result(json_out, result)
    if failures:
        print(f"IDENTITY MISMATCH on {len(failures)} file(s)", file=sys.stderr)
        return 1
    print(
        f"model revision and all recorded file identities verified "
        f"(direct modes: {','.join(result['read_modes'])}; ordinary cache "
        "path also matched)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
