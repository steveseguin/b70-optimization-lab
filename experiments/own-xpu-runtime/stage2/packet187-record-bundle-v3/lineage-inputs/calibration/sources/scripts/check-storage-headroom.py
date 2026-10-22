#!/usr/bin/env python3
"""Read-only Linux storage admission check; never creates output directories.

Examples (run immediately before the writing job, joined with &&):
  python3 scripts/check-storage-headroom.py /path/to/new/run \
      --min-free-bytes 50GiB --planned-write-bytes 10GiB
  python3 scripts/check-storage-headroom.py /mnt/usb-models/archive/new \
      --require-mount /mnt/usb-models --planned-write-bytes 100GiB

Pass --require-mount for external destinations: an unmounted directory must not
silently admit writes to its parent filesystem. Symlinks are resolved before
checking containment and the actual filesystem. Budget peak additional writes,
including temporary copies, logs, caches and concurrent jobs on this filesystem.
Run a separate check for every other output/cache filesystem a job uses.

JSON goes to stdout. Exit 0 means admitted, 1 means refused, 2 means invalid
arguments or an inspection error. This is a point-in-time check, not a space
reservation or a disk-health/backup verification.
"""

import argparse
import json
import os
from pathlib import Path
import re
import stat


def byte_count(value: str) -> int:
    """Accept whole bytes or integer SI/IEC units, without rounding down."""
    match = re.fullmatch(r"([0-9]+)(B|[KMGT]i?B)?", value)
    if not match:
        raise argparse.ArgumentTypeError("use whole bytes or integer units, e.g. 50GiB")
    amount, unit = match.groups()
    if not unit or unit == "B":
        return int(amount)
    return int(amount) * (1024 if "i" in unit else 1000) ** ("KMGT".index(unit[0]) + 1)


def mount_unescape(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)


def read_mounts() -> list[dict]:
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        separator = fields.index("-")
        mounts.append({
            "mount_id": int(fields[0]),
            "mount_point": mount_unescape(fields[4]),
            "filesystem_type": fields[separator + 1],
            "source": mount_unescape(fields[separator + 2]),
        })
    if not mounts:
        raise OSError("empty mount table")
    return mounts


def containing_mount(path: Path, mounts: list[dict]) -> dict:
    candidates = [m for m in mounts if path.is_relative_to(Path(m["mount_point"]))]
    if not candidates:
        raise OSError(f"cannot identify filesystem for {path}")
    return max(candidates, key=lambda m: (len(Path(m["mount_point"]).parts), m["mount_id"]))


def inspect_destination(destination: Path, min_free: int, planned_write: int,
                        require_mount: Path | None = None) -> dict:
    if min_free < 0 or planned_write < 0:
        raise ValueError("byte budgets must be nonnegative")
    resolved = destination.expanduser().resolve()
    existing = resolved
    while True:
        try:
            mode = existing.stat().st_mode
            break
        except FileNotFoundError:
            if existing == existing.parent:
                raise
            existing = existing.parent
    if not (stat.S_ISDIR(mode) or (existing == resolved and stat.S_ISREG(mode))):
        raise ValueError(f"destination or its ancestor is not a directory/file: {existing}")
    mounts = read_mounts()
    actual_mount = containing_mount(existing, mounts)
    stats = os.statvfs(existing)
    available = stats.f_bavail * stats.f_frsize
    required = min_free + planned_write
    failures = []
    expected = None
    if require_mount is not None:
        expected = require_mount.expanduser().resolve()
        if not resolved.is_relative_to(expected):
            failures.append(f"resolved destination is outside required mount {expected}")
        roots = [m for m in mounts if Path(m["mount_point"]) == expected]
        if not roots:
            failures.append(f"required root is not mounted: {expected}")
        elif actual_mount["mount_id"] != max(roots, key=lambda m: m["mount_id"])["mount_id"]:
            failures.append("destination is on a different mount than the required root")
    if stats.f_flag & os.ST_RDONLY:
        failures.append("destination filesystem is read-only")
    if available < required:
        failures.append(f"insufficient space: need {required - available} additional bytes")
    return {
        "schema_version": 1,
        "admitted": not failures,
        "destination": str(destination),
        "resolved_destination": str(resolved),
        "checked_existing_path": str(existing),
        "required_mount": str(expected) if expected is not None else None,
        "filesystem": actual_mount,
        "available_bytes": available,
        "min_free_bytes": min_free,
        "planned_write_bytes": planned_write,
        "required_bytes": required,
        "remaining_after_planned_write_bytes": available - planned_write,
        "failures": failures,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("destination", type=Path, help="output file or directory; need not exist yet")
    parser.add_argument("--min-free-bytes", type=byte_count, default=50 * 1024**3,
                        help="free-space floor after planned writes (default: 50GiB)")
    parser.add_argument("--planned-write-bytes", type=byte_count, required=True,
                        help="peak additional writes, including temporary files; accepts 10GiB or bytes")
    parser.add_argument("--require-mount", type=Path,
                        help="require this exact mount root and keep resolved writes on it")
    args = parser.parse_args(argv)
    try:
        report = inspect_destination(args.destination, args.min_free_bytes,
                                     args.planned_write_bytes, args.require_mount)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"schema_version": 1, "admitted": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
