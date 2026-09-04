#!/usr/bin/env python3
"""Create the A115 packet from frozen A114: the byte-identical fresh-server repeat of the MTP1 promotion candidate.

A115 keeps every A114 file unchanged apart from the attempt number, port and
state names, so a second independently started server runs the same frozen
MTP1 client against the same pins. Attempt 115 / port 19787.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A115_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh': '8707f64b54aa4d6763b4c0acac2d87f810b8f572de0864d172a1ccf1963a4396',
    'run-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32-client.sh': '62525b13384be6a9809ae99be794dcd73ffed436b88a7a0bf2ccdea6ecc3ad21',
    'supervise-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh': '21c3102d4674005e20ddeaa8e5db02982e05f919eb9b98f8c58be38da7e8c5e9',
    'run-q38-a114-host-controlled.sh': '080797438c346d06909fb596e46c78500ee5959f4b6d407322014685cda09e05',
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60"

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a114", "tp4-mtp1-4352-ple-only-a115")
        seg = seg.replace("attempt114", "attempt115").replace("19786", "19787")
        seg = seg.replace("ATTEMPT=114", "ATTEMPT=115").replace("a114", "a115").replace("A114", "A115")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19786" not in out and "attempt114" not in out
    return out
def replace_once(t, a, b):
    assert t.count(a) == 1, (t.count(a), a[:80]); return t.replace(a, b)
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:80]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)

def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A115_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a115-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a115" in derived and NEW_HEAD in derived and OLD_HEAD not in derived
    assert "ATTEMPT=115 PORT=19787" in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a114-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp1-4352-ple-only-a114-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a115-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a115-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a115-fullgraphdet-w13n32.sh", "run-q38-a115-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
