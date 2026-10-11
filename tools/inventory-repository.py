#!/usr/bin/env python3
"""Inventory repository files without following symlinks or changing any inputs.

The census includes ignored files and nested repository metadata. It classifies
file roles, not scientific value: duplicate bytes are never deletion approval.
Only the explicitly requested, new output directory is written.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


def git(root, *args, input=None):
    return subprocess.run(["git", "-C", str(root), *args], input=input,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def role(path):
    p = Path(path)
    if ".git" in p.parts:
        return "nested-git-metadata"
    if "__pycache__" in p.parts or p.suffix in {".pyc", ".pyo"} or ".ruff_cache" in p.parts:
        return "generated-cache-review"
    if p.suffix in {".bundle", ".patch", ".diff"} or p.parts[0] == "patches":
        return "patch-or-source-provenance"
    if p.suffix in {".so", ".a", ".o", ".whl"}:
        return "binary-or-build-artifact-review"
    if p.suffix in {".md", ".rst", ".txt", ".html"}:
        return "narrative-or-document"
    if p.suffix in {".json", ".jsonl", ".csv", ".tsv", ".log", ".gz", ".zip", ".xz"}:
        return "data-log-manifest-or-archive"
    if p.suffix in {".py", ".sh", ".cpp", ".cc", ".h", ".hpp", ".c", ".js", ".toml", ".yaml", ".yml"}:
        return "source-script-or-configuration"
    return "other-retain-for-review"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inventory(root, output):
    root = root.resolve()
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a new directory")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    started = datetime.now(timezone.utc).isoformat()
    head = git(root, "rev-parse", "HEAD").decode().strip()
    index = {}
    for raw in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not raw:
            continue
        meta, name = raw.split(b"\t", 1)
        mode, oid, stage = meta.decode().split()
        if stage != "0":
            raise ValueError("Unmerged index; resolve it before taking an inventory")
        index[os.fsdecode(name)] = {"git_mode": mode, "git_blob": oid}

    paths = []
    problems = []

    def walk_error(error):
        problems.append({"path": str(error.filename), "reason": str(error)})

    root_git = {"files": 0, "logical_bytes": 0, "allocated_bytes": 0}
    boundaries = []
    for base, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        base = Path(base)
        if base == root:
            dirs[:] = [d for d in dirs if d != ".git"]
        for name in list(dirs):
            p = base / name
            if p == output or output in p.parents:
                dirs.remove(name)
            elif p.is_symlink():
                paths.append(p)
                dirs.remove(name)
            elif name == ".git":
                boundaries.append(str(p.parent.relative_to(root)))
        paths.extend(base / name for name in files)
    for base, _, files in os.walk(root / ".git", followlinks=False, onerror=walk_error):
        for name in files:
            try:
                s = (Path(base) / name).lstat()
            except OSError as exc:
                walk_error(exc)
                continue
            root_git["files"] += 1
            root_git["logical_bytes"] += s.st_size
            root_git["allocated_bytes"] += s.st_blocks * 512
    paths.sort()
    rels = [str(p.relative_to(root)) for p in paths]
    missing_index = sorted(set(index) - set(rels))
    candidates = [p for p in rels if p not in index]
    ignored = set()
    # check-ignore expands ignored parent directories and nested checkout paths,
    # unlike relying on a flat ls-files --others listing alone.
    for offset in range(0, len(candidates), 5000):
        batch = candidates[offset:offset + 5000]
        result = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-z", "--stdin"],
                                input=b"\0".join(os.fsencode(x) for x in batch) + b"\0",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode not in (0, 1):
            raise ValueError(result.stderr.decode(errors="replace"))
        ignored.update(os.fsdecode(x) for x in result.stdout.split(b"\0") if x)

    groups = defaultdict(list)
    totals = Counter()
    areas = defaultdict(Counter)
    roles = defaultdict(Counter)
    largest = []
    with gzip.open(output / "files.jsonl.gz", "wt", encoding="utf-8") as stream:
        for p, rel in zip(paths, rels):
            row = {"path": rel, "git_state": "tracked" if rel in index else "ignored" if rel in ignored else "untracked",
                   "role": role(rel), "disposition": "retain-unless-explicitly-reviewed", **index.get(rel, {})}
            try:
                before = p.lstat()
                row.update(bytes=before.st_size, allocated_bytes=before.st_blocks * 512,
                           mtime_ns=before.st_mtime_ns, device=before.st_dev,
                           inode=before.st_ino, links=before.st_nlink, mode=stat.S_IMODE(before.st_mode))
                if stat.S_ISLNK(before.st_mode):
                    row.update(kind="symlink", target=os.readlink(p))
                    row["sha256"] = hashlib.sha256(os.fsencode(row["target"])).hexdigest()
                elif stat.S_ISREG(before.st_mode):
                    row["kind"] = "file"
                    h = hashlib.sha256()
                    descriptor = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(descriptor, "rb") as source:
                        if stamp(os.fstat(source.fileno())) != stamp(before):
                            raise OSError("File was replaced before hashing")
                        for block in iter(lambda: source.read(1024 * 1024), b""):
                            h.update(block)
                        if stamp(os.fstat(source.fileno())) != stamp(before):
                            raise OSError("File changed while hashing")
                    row["sha256"] = h.hexdigest()
                else:
                    row["kind"] = "special-not-read"
                row["stable_during_read"] = stamp(before) == stamp(p.lstat())
                if not row["stable_during_read"]:
                    problems.append({"path": rel, "reason": "changed during read"})
                elif row["kind"] == "file" and row["bytes"] >= 1024:
                    groups[(row["sha256"], row["bytes"])].append(rel)
            except OSError as exc:
                row["error"] = str(exc)
                problems.append({"path": rel, "reason": str(exc)})
            parts = Path(rel).parts
            area = "/".join(parts[:2]) if len(parts) > 2 and parts[0] in {"experiments", "patches", "results", "repro", "packages", "community"} else parts[0] if len(parts) > 1 else "(root files)"
            for counter in (totals, areas[area], roles[row["role"]]):
                counter["files"] += 1
                counter["logical_bytes"] += row.get("bytes", 0)
                counter["allocated_bytes"] += row.get("allocated_bytes", 0)
                counter[row["git_state"] + "_files"] += 1
            largest.append({k: row[k] for k in ("path", "bytes", "git_state", "role") if k in row})
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    duplicates = [{"sha256": sha, "bytes_each": size, "logical_excess_bytes": size * (len(names) - 1),
                   "paths": names, "action": "review-dependencies-before-any-deduplication"}
                  for (sha, size), names in groups.items() if len(names) > 1]
    duplicates.sort(key=lambda x: (-x["logical_excess_bytes"], x["sha256"]))
    with gzip.open(output / "duplicates.jsonl.gz", "wt", encoding="utf-8") as stream:
        for row in duplicates:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    end_head = git(root, "rev-parse", "HEAD").decode().strip()
    summary = {"schema": "lab.repository-inventory.v1", "root": str(root), "started_utc": started,
               "finished_utc": datetime.now(timezone.utc).isoformat(), "source_commit": head,
               "end_commit": end_head, "commit_stable": head == end_head,
               "scope": "Repository files, including ignored files and nested Git metadata; no symlink targets followed.",
               "excluded": ["Root .git content (size only)", str(output)],
               "semantic_review_complete": False, "deletion_authorized_by_inventory": False,
               "git_index_entries": len(index), "index_paths_not_walked": missing_index,
               "totals": dict(totals), "root_git": root_git, "nested_repositories": sorted(boundaries),
               "areas": {k: dict(v) for k, v in sorted(areas.items())},
               "roles": {k: dict(v) for k, v in sorted(roles.items())},
               "duplicate_groups": len(duplicates),
               "duplicate_minimum_bytes": 1024,
               "duplicate_logical_excess_bytes": sum(x["logical_excess_bytes"] for x in duplicates),
               "duplicate_caveat": "Not reclaimable space: shared inodes and sealed or separately required copies need review; Git already deduplicates identical blobs.",
               "largest_files": sorted(largest, key=lambda x: -x.get("bytes", 0))[:40],
               "problems": problems,
               "artifacts": {name: {"bytes": (output / name).stat().st_size,
                                     "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
                             for name in ("files.jsonl.gz", "duplicates.jsonl.gz")}}
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.repo, args.output)
    print(json.dumps({"output": str(args.output), "totals": result["totals"],
                      "duplicate_groups": result["duplicate_groups"], "problems": result["problems"],
                      "commit_stable": result["commit_stable"]}, ensure_ascii=False, indent=2))
    return 1 if (result["problems"] or result["index_paths_not_walked"]
                 or not result["commit_stable"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
