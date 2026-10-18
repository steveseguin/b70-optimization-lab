#!/usr/bin/env python3
"""Archive reviewed CLOSED screen bulk, verify every byte, then unlink only it."""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = Path("experiments/own-xpu-runtime")
BULK = ("run/adapter/build/driver-cache", "run/input-bundles")
ARCHIVE = Path("/mnt/raid-models/own-xpu-runtime-archive/screen-bulk")
SHA = re.compile(r"^[0-9a-fA-F]{64}$")
PACKET = re.compile(r"^(?:packet|p)([0-9]+[a-z]*)(?:-|$)")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_stream(stream):
    h = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def digest(path):
    with path.open("rb") as stream:
        return digest_stream(stream)[0]


def read(path):
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"not a JSON object: {path}")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def resolve(root, path):
    p = Path(path)
    return (p if p.is_absolute() else root / p).resolve()


def no_symlinks(path, root):
    require(path.is_relative_to(root), f"outside root: {path}")
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"symlink refused: {part}")
        if part == root:
            break


def packet(path):
    # Outermost packet owns nested compat/packet64 and selection trees.
    for part in path.parts:
        match = PACKET.match(part)
        if match:
            return match[1]
    return None


def closed(path, config):
    item = config["packets"].get(packet(path), {})
    if item.get("status") != "CLOSED":
        return False
    views = item.get("views")
    if views is None:
        return True
    # Partial closure is deliberately literal: H1 cannot close E1/production.
    return any(part == view or part.endswith("-" + view)
               for part in path.parts for view in views)


def config_read(path):
    value = read(path)
    require(isinstance(value.get("packets"), dict), "packets map required")
    for number, item in value["packets"].items():
        require(re.fullmatch(r"[0-9]+[a-z]*", number), "invalid packet id")
        require(item.get("status") == "CLOSED" and item.get("reason"), "explained CLOSED entry required")
        if "views" in item:
            require(isinstance(item["views"], list) and item["views"] and
                    all(isinstance(v, str) and re.fullmatch(r"[a-z0-9+-]+", v) for v in item["views"]), "invalid view closure")
    require(isinstance(value.get("reviewed_jobs", []), list), "reviewed_jobs list required")
    return value


def documents(runtime, follow_links=False):
    # Live packet evidence may be linked into the external results tree. Read
    # it too, once per real directory; fail on unreadable trees or broken links.
    # Candidate screen trees never permit links, and builds are not pruned.
    def error(exc):
        raise exc
    seen = set()
    for directory, dirs, files in os.walk(runtime, followlinks=follow_links, onerror=error):
        real = Path(directory).resolve()
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        for name in dirs:
            link = Path(directory) / name
            if link.is_symlink():
                require(follow_links and link.exists(), f"linked/broken evidence directory: {link}")
        for name in files:
            if name == "window.json" or ("identity" in name and name.endswith(".json")):
                yield Path(directory) / name


def protections(root, config):
    """Protect by both named path and digest, including anonymous identity hashes."""
    paths, hashes, receipts = set(), set(), {}
    def walk(value, base):
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, str) and SHA.fullmatch(child):
                    if "/" in key or "." in key:
                        paths.update((resolve(root, key), resolve(base, key)))
                    elif key.endswith('_sha256') and isinstance(value.get(key[:-7]), str) and '/' in value[key[:-7]]:
                        target = value[key[:-7]]
                        paths.update((resolve(root, target), resolve(base, target)))
                    else:
                        # A digest without a named file cannot safely be tied
                        # to one location: retain every matching candidate.
                        hashes.add(child.lower())
                    continue
                walk(child, base)
        elif isinstance(value, list):
            for child in value:
                walk(child, base)
        elif isinstance(value, str):
            if SHA.fullmatch(value):
                hashes.add(value.lower())
            elif "/" in value and "\n" not in value and len(value) < 4096:
                paths.update((resolve(root, value), resolve(base, value)))
    for path in documents(root / RUNTIME, follow_links=True):
        # Some packets link screen/ to the shared v4 tree. Ownership follows
        # the real screen path, not the packet that supplied that alias.
        real = path.resolve()
        owner = real if real.is_relative_to(root / RUNTIME) else path
        if closed(owner.relative_to(root / RUNTIME), config):
            continue
        require(path.resolve().is_file(), f"missing live window/identity: {path}")
        data = path.read_bytes()
        value = json.loads(data)
        require(isinstance(value, dict), f"invalid live identity/window: {path}")
        receipts[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
        walk(value, path.parent)
    return paths, hashes, receipts


def done_reviews(root, config):
    """A fault preflight alone is not a post-screen review."""
    queue = root / RUNTIME / "ops/lane-queue"
    result = {}
    for ledger in sorted(queue.glob("done-*.txt")):
        no_symlinks(ledger, root)
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            job = row["job"]
            reviewed = "-reviewed-" in ledger.name or job["name"] in config.get("reviewed_jobs", [])
            if row.get("outcome") != "DONE" or not reviewed:
                continue
            require(row.get("rc") == 0 and row.get("Result") == "success" and str(row.get("ExecMainStatus")) == "0", "inconsistent DONE: " + job["name"])
            review = resolve(root, row["review"])
            no_symlinks(review, root)
            key = hashlib.sha256(canonical(read(review))).hexdigest()
            result.setdefault(key, []).append(dict(ledger=str(ledger.relative_to(root)),
                completion_sha256=hashlib.sha256(line.encode()).hexdigest(), job=job))
    return result


def runs(root):
    stage = root / RUNTIME / "stage2/screen"
    for version in ("v4-lanes", "v5-bracket"):
        evidence = stage / version / "evidence"
        if evidence.exists():
            for path in documents(evidence):
                if path.name == "window.json":
                    yield path.parent


def finished_review(root, run, reviews):
    window = read(run / "window.json")
    # Packet86 diagnostics deliberately fail the model quality gate and lack
    # finished_utc_ns, even with a completed, drained device run and DONE job.
    finished = window.get("finished_utc_ns") or (window.get('device_complete') is True and
               window.get('lease_released') is True and window.get('returncode') == 0)
    require(finished and not window.get("child_still_running") and
            not window.get("child_retained"), "screen unfinished or child retained")
    key = hashlib.sha256(canonical(window.get("coordinator_fault_review"))).hexdigest()
    matched = []
    for receipt in reviews.get(key, []):
        job = receipt["job"]
        if job.get("lane") != window.get("lane"):
            continue
        args = job.get("argv", [])
        outputs = [args[i+1] for i, arg in enumerate(args[:-1]) if arg == "--output"]
        outputs += [arg.split("=", 1)[1] for arg in args if arg.startswith("--output=")]
        # A grouped runner shares its unique review across the bracket. Explicit
        # output jobs must also match exactly (v5 may contain per-view children).
        if outputs and not any(run.is_relative_to(resolve(root, out)) for out in outputs):
            continue
        matched.append(receipt)
    require(len(matched) == 1, "no unique reviewed DONE job for screen")
    return matched[0]


def fingerprint(path):
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode), f"non-regular bulk file: {path}")
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink]


def plan(root, config_path):
    config = config_read(config_path)
    protected_paths, protected_hashes, pins = protections(root, config)
    reviews = done_reviews(root, config)
    result = dict(schema="own-runtime.screen-cleanup.v1", plan=True, runs=[],
                  closed_sha256=digest(config_path), live_documents=pins)
    for run in sorted(runs(root)):
        if not closed(run.relative_to(root / RUNTIME), config):
            continue
        row = dict(run=str(run.relative_to(root)), files=[], retained=[], bytes=0)
        result["runs"].append(row)
        try:
            no_symlinks(run, root)
            row["completion"] = finished_review(root, run, reviews)
            row["window_sha256"] = digest(run / "window.json")
        except (ValueError, OSError, KeyError) as exc:
            row.update(status="SKIP", reason=str(exc))
            continue
        for bulk in BULK:
            directory = run / bulk
            no_symlinks(directory, root)
            if not directory.exists():
                continue  # Previous manual archive is already done.
            for base, dirs, files in os.walk(directory, followlinks=False):
                for name in dirs:
                    no_symlinks(Path(base) / name, root)
                for name in sorted(files):
                    path = Path(base) / name
                    no_symlinks(path, root)
                    rel = str(path.relative_to(run))
                    before = fingerprint(path)
                    if path.name.lower().endswith((".json", ".jsonl", ".json.gz", ".jsonl.gz")):
                        row["retained"].append(dict(path=rel, reason="JSON receipt"))
                        continue
                    sha = digest(path)
                    require(fingerprint(path) == before, f"bulk changed during read: {path}")
                    if path.resolve() in protected_paths or sha in protected_hashes:
                        row["retained"].append(dict(path=rel, reason="live window/identity reference"))
                        continue
                    row["files"].append(dict(path=rel, sha256=sha, size=before[2], fingerprint=before))
                    row["bytes"] += before[2]
        row["status"] = "ARCHIVE" if row["files"] else "DONE"
    result["bytes"] = sum(r["bytes"] for r in result["runs"])
    # Logical bytes count hard links separately. Reclaim is only an estimate:
    # external links mean unlinking these names releases no blocks.
    inodes = {}
    for row in result["runs"]:
        for f in row["files"]:
            key = tuple(f["fingerprint"][:2])
            inodes.setdefault(key, []).append(f)
    result["reclaimable_bytes_estimate"] = sum(fs[0]["size"] for fs in inodes.values()
                                              if len(fs) == fs[0]["fingerprint"][-1])
    return result


def verify_archive(archive, manifest):
    """Read actual stored content for EVERY member, including tar hard links."""
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        expected = [f["path"] for f in manifest["files"]] + ["MANIFEST.json"]
        require(len(names) == len(set(names)) and set(names) == set(expected), "archive member set differs")
        require(json.load(tar.extractfile("MANIFEST.json")) == manifest, "archive manifest differs")
        for f in manifest["files"]:
            member = tar.getmember(f["path"])
            require(member.isfile() or member.islnk(), "archive contains non-file member")
            if member.islnk():
                require(member.linkname in expected and member.linkname != "MANIFEST.json", "hard link escapes archive files")
            with tar.extractfile(member) as stream:
                sha, size = digest_stream(stream)
            require((sha, size) == (f["sha256"], f["size"]), "archive content differs: " + f["path"])


def archive_run(root, row, archive_dir):
    run = root / row["run"]
    no_symlinks(archive_dir, Path('/'))
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest = dict(schema="own-runtime.screen-bulk.v1", run=row["run"],
                    completion=row["completion"], window_sha256=row["window_sha256"],
                    files=[{k: f[k] for k in ("path", "sha256", "size")} for f in row["files"]])
    name = run.name + "-" + hashlib.sha256(row["run"].encode()).hexdigest()[:16]
    archive = archive_dir / (name + ".tar.gz")
    sidecar = archive_dir / (name + ".manifest.json")
    no_symlinks(archive, Path('/'))
    no_symlinks(sidecar, Path('/'))
    if archive.exists():
        require(sidecar.is_file(), "existing archive missing manifest; manual review required")
        old = read(sidecar)
        require(old["run"] == manifest["run"] and old["completion"] == manifest["completion"] and
                old["window_sha256"] == manifest["window_sha256"], "existing archive identity differs")
        require(all(f in old["files"] for f in manifest["files"]), "existing archive lacks remaining file")
        verify_archive(archive, old)  # Resume after partially completed deletion.
        return archive
    require(not sidecar.exists(), "orphan manifest requires review")
    fd, temp = tempfile.mkstemp(prefix=name + ".", suffix=".partial", dir=archive_dir)
    os.close(fd)
    temp = Path(temp)
    try:
        with tarfile.open(temp, "w:gz", dereference=False) as tar:
            for f in row["files"]:
                path = run / f["path"]
                no_symlinks(path, root)
                require(fingerprint(path) == f["fingerprint"], "source changed before archive")
                tar.add(path, arcname=f["path"], recursive=False)
            data = canonical(manifest)
            info = tarfile.TarInfo("MANIFEST.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        verify_archive(temp, manifest)
        with temp.open("rb") as stream:
            os.fsync(stream.fileno())
        # Do not overwrite a prior archive, even if another invocation races.
        os.link(temp, archive)
        with sidecar.open("x") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        dirfd = os.open(archive_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        temp.unlink(missing_ok=True)
    return archive


def execute(root, config_path, archive_dir):
    # Coordinator-only. Separate lock; never open or edit the lane queues.
    archive_dir = archive_dir.absolute()
    no_symlinks(archive_dir, Path('/'))
    require(not archive_dir.is_relative_to(root), "archive must be outside the repository")
    if archive_dir == ARCHIVE:
        require(Path('/mnt/raid-models').is_mount(), 'archive disk is not mounted')
    archive_dir.mkdir(parents=True, exist_ok=True)
    with (archive_dir / ".cleanup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial = plan(root, config_path)
        archives = {}
        # Archive the entire admitted set before deleting any member. This
        # also preserves cross-run hard links without repeated full scans.
        for row in initial["runs"]:
            if row["status"] == "ARCHIVE":
                archives[row["run"]] = archive_run(root, row, archive_dir)
        if archives:
            # Re-read ALL live packet identities and completion/closure state
            # after full archive verification, immediately before any unlink.
            current = plan(root, config_path)
            require(current["closed_sha256"] == initial["closed_sha256"], "closure changed; no deletion")
            for row in initial["runs"]:
                if row["run"] in archives:
                    now = next((r for r in current["runs"] if r["run"] == row["run"]), None)
                    require(now == row, "eligibility or source changed; no deletion")
            for row in initial["runs"]:
                if row["run"] not in archives:
                    continue
                for f in row["files"]:
                    path = root / row["run"] / f["path"]
                    no_symlinks(path, root)
                    # ctime/nlink change when a sibling hard link is removed.
                    require(fingerprint(path)[:4] == f["fingerprint"][:4] and digest(path) == f["sha256"], "source changed before deletion")
                    path.unlink()
                row.update(status="ARCHIVED", archive=str(archives[row["run"]]))
        initial["plan"] = False
        return initial


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true", help="coordinator only: archive, verify and delete")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--closed", type=Path, default=Path(__file__).with_name("closed.json"))
    ap.add_argument("--archive-root", type=Path, default=ARCHIVE)
    args = ap.parse_args()
    root = args.root.resolve()
    result = plan(root, args.closed) if args.plan else execute(root, args.closed, args.archive_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
