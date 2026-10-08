#!/usr/bin/env python3
"""Tier A: retire stopped stream-01 previews and (archived) request dirs.

From notes/2026-10-08-storage-reclaim-plan.md section 5, with these changes made
for the 2026-10-08 execution (owner approval: "run the verify then delete script"):
  * no systemctl call: the stop is proven by data/resume-20261008/stream01-stop.json
    plus a /proc cmdline scan (no process names the unit or the stream01 prefix);
  * archive path /home/steve/git-archives/ltx-stream01-requests-20261008.tar.zst;
    after `tar --compare`, the archive listing must equal the planned file list
    exactly; the listing is written next to the archive and hashed in the receipt;
  * a /proc fd scan before the first unlink; refuses if free space < 50 GiB.
plan  : python3 -B tier_a.py plan  --out PLAN.json [--include-requests]
apply : python3 -B tier_a.py apply --plan PLAN.json --sha256 <plan sha> --receipt RECEIPT.json
"""
import argparse, hashlib, json, os, re, subprocess, sys, time

ROOT = os.environ.get("TIER_A_TEST_ROOT", "/mnt/fast-ai/bench-results/ltx25-baseline-20260913")
TAR = os.environ.get("TIER_A_TEST_TAR", "/home/steve/git-archives/ltx-stream01-requests-20261008.tar.zst")
STOP = os.environ.get("TIER_A_TEST_STOP", "/home/steve/llm-optimizations/experiments/ltx25-b70/data/resume-20261008/stream01-stop.json")
PREFIX = "s97-twowayw2b2p1dxpu2-stream01"
PREV_RE = re.compile(r"^s97-twowayw2b2p1dxpu2-stream01-\d{7}$")
PREV_FILE_RE = re.compile(r"^preview_\d{5}_\.mp4$")
REQ_FILES = {"history.json", "identity.json", "prompt.json", "result.json", "submission.json"}
PROTECT_RE = re.compile(r"stability-|-ref-|-ref$|proof|wself|archive-|/validation/|quarantine|prepared-|encoder-server-")
UNIT = "ltx97-stream01-server-20261008"
RESERVE = 50 * 2**30

def die(msg):
    print("REFUSED:", msg, file=sys.stderr); sys.exit(2)

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def st(path):
    s = os.lstat(path)
    return {"size": s.st_size, "blocks512": s.st_blocks, "ino": s.st_ino, "dev": s.st_dev,
            "nlink": s.st_nlink, "mtime_ns": s.st_mtime_ns, "mode": s.st_mode}

def stream_stopped():
    stop = json.load(open(STOP))
    if stop.get("unit") != UNIT or not stop.get("stop_utc"):
        return False
    own = {os.getpid(), os.getppid()}
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) in own:
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if UNIT in cmd or PREFIX in cmd:
            return False
    return True

def open_inodes():
    seen = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                s = os.stat(f"/proc/{pid}/fd/{fd}"); seen.add((s.st_dev, s.st_ino))
            except OSError:
                pass
    return seen

def free_bytes():
    v = os.statvfs(ROOT); return v.f_bavail * v.f_frsize

def fsync_write(path, obj, exclusive=True):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC), 0o644)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True); f.flush(); os.fsync(f.fileno())
    dfd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY); os.fsync(dfd); os.close(dfd)

def enumerate_targets(include_requests):
    files = []
    out = os.path.join(ROOT, "output")
    for d in sorted(os.listdir(out)):
        if not PREV_RE.match(d):
            continue
        p = os.path.join(out, d)
        ents = os.listdir(p)
        if len(ents) != 1 or not PREV_FILE_RE.match(ents[0]):
            die(f"unexpected contents in {p}: {ents}")
        files.append(("A1", os.path.join(p, ents[0])))
    reqdirs = []
    if include_requests:
        rq = os.path.join(ROOT, "requests")
        for d in sorted(os.listdir(rq)):
            if not PREV_RE.match(d):
                continue
            p = os.path.join(rq, d)
            if set(os.listdir(p)) - REQ_FILES:
                die(f"unexpected contents in {p}")
            reqdirs.append(p)
            for n in sorted(os.listdir(p)):
                files.append(("A2", os.path.join(p, n)))
    for _, f in files:
        if PROTECT_RE.search(f):
            die(f"protected-looking path selected: {f}")
        s = os.lstat(f)
        if not os.path.isfile(f) or os.path.islink(f) or s.st_nlink != 1:
            die(f"not a plain single-link file: {f}")
    return files, reqdirs

def cmd_plan(a):
    if not stream_stopped():
        die(f"{UNIT} not proven stopped")
    files, reqdirs = enumerate_targets(a.include_requests)
    entries = [{"set": k, "path": f, "sha256": sha(f), **st(f)} for k, f in files]
    plan = {"schema": "ltx.tier-a-stream01.v1", "root": ROOT, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "include_requests": a.include_requests, "request_dirs": reqdirs, "tar": TAR if a.include_requests else None,
            "counts": {k: sum(1 for e in entries if e["set"] == k) for k in ("A1", "A2")},
            "allocated_bytes": sum(e["blocks512"] * 512 for e in entries),
            "free_bytes_at_plan": free_bytes(), "files": entries}
    fsync_write(a.out, plan)
    print("plan", a.out, "sha256", sha(a.out), plan["counts"], plan["allocated_bytes"])

def cmd_apply(a):
    if sha(a.plan) != a.sha256:
        die("plan sha256 mismatch")
    plan = json.load(open(a.plan))
    if plan["root"] != ROOT:
        die("plan root differs")
    if not stream_stopped():
        die(f"{UNIT} not proven stopped")
    if free_bytes() < RESERVE:
        die("free space below 50 GiB reserve")
    receipt = a.receipt
    for p in (receipt, receipt + ".intent.json", receipt + ".events.jsonl"):
        if os.path.exists(p):
            die(f"{p} exists; no automatic retry")
    cur, reqdirs = enumerate_targets(plan["include_requests"])
    if sorted(f for _, f in cur) != sorted(e["path"] for e in plan["files"]) or reqdirs != plan["request_dirs"]:
        die("current file set differs from plan (re-plan)")
    for e in plan["files"]:                       # verification pass 2: nothing removed yet
        s = st(e["path"])
        for k in ("size", "ino", "dev", "nlink", "mtime_ns"):
            if s[k] != e[k]:
                die(f"stat changed: {e['path']} {k}")
        if sha(e["path"]) != e["sha256"]:
            die(f"content changed: {e['path']}")
    listing = None
    if plan["include_requests"]:
        if os.path.exists(TAR) or os.path.exists(TAR + ".list"):
            die(f"{TAR} exists; refusing to overwrite")
        rel = [os.path.relpath(d, ROOT) for d in reqdirs]
        subprocess.run(["tar", "--zstd", "-cf", TAR, "-C", ROOT, *rel], check=True)
        subprocess.run(["sync", TAR], check=True)
        subprocess.run(["tar", "--zstd", "--compare", "-f", TAR, "-C", ROOT], check=True)
        names = subprocess.run(["tar", "--zstd", "-tf", TAR], check=True, capture_output=True, text=True).stdout.split("\n")
        got = sorted(n.rstrip("/") for n in names if n and not n.endswith("/"))
        want = sorted(os.path.relpath(e["path"], ROOT) for e in plan["files"] if e["set"] == "A2")
        dirs = sorted(n.rstrip("/") for n in names if n.endswith("/"))
        if got != want or dirs != sorted(rel):
            die("archive listing differs from planned request files")
        with open(TAR + ".list", "x") as f:
            f.write("\n".join(got) + "\n"); f.flush(); os.fsync(f.fileno())
        listing = {"path": TAR + ".list", "sha256": sha(TAR + ".list"), "files": len(got), "dirs": len(dirs)}
    opened = open_inodes()
    for e in plan["files"]:
        if (e["dev"], e["ino"]) in opened:
            die(f"file is open by a process: {e['path']}")
    intent = {"plan": os.path.abspath(a.plan), "plan_sha256": a.sha256, "tar": TAR if plan["include_requests"] else None,
              "tar_sha256": sha(TAR) if plan["include_requests"] else None, "tar_listing": listing,
              "tar_compare": "passed" if plan["include_requests"] else None,
              "free_bytes_before": free_bytes(), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    fsync_write(receipt + ".intent.json", intent)
    ev = open(receipt + ".events.jsonl", "x")
    done = []
    for e in plan["files"]:
        os.unlink(e["path"])
        ev.write(json.dumps({"unlinked": e["path"], "sha256": e["sha256"]}) + "\n"); ev.flush(); os.fsync(ev.fileno())
        done.append(e["path"])
    dirs = sorted({os.path.dirname(p) for p in done})
    for d in dirs:
        os.rmdir(d)                                # fails (and stops) if anything unexpected remains
    ev.close()
    fsync_write(receipt, {**intent, "status": "completed", "unlinked": len(done), "rmdir": len(dirs),
                          "counts": plan["counts"], "allocated_bytes": plan["allocated_bytes"],
                          "free_bytes_after": free_bytes(), "events_sha256": sha(receipt + ".events.jsonl"),
                          "restore": "A2: tar --zstd -xf TAR -C ROOT (refuses nothing; check paths absent first). A1 previews are not restorable; hashes are in the plan.",
                          "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print("completed", len(done), "files", len(dirs), "dirs")

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("plan"); p.add_argument("--out", required=True); p.add_argument("--include-requests", action="store_true")
q = sp.add_parser("apply"); q.add_argument("--plan", required=True); q.add_argument("--sha256", required=True); q.add_argument("--receipt", required=True)
a = ap.parse_args(); {"plan": cmd_plan, "apply": cmd_apply}[a.cmd](a)
