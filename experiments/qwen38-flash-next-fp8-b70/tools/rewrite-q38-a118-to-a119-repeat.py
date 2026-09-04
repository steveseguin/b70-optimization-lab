#!/usr/bin/env python3
"""Create the A119 packet from frozen A118: the byte-identical fresh-server repeat of the MTP1 promotion candidate.

A119 keeps every A118 file unchanged apart from the attempt number, port and
state names, so a second independently started server runs the same frozen
MTP1 client against the same pins. Attempt 115 / port 19791.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A119_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh': 'c7aa6d24ffd33bef3bebc459dfa52a4af03b52023ea4f190c8186a0fb9d7776a',
    'run-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32-client.sh': '2c7f70b075669e728bdb44d1f17a6670dee0eb1cd0d6ca41434568420f82ebef',
    'supervise-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh': 'f642e725b0ae39af2c074647e9f66e6cd5e1c675a81bbdcdc538cb66911ef340',
    'run-q38-a118-host-controlled.sh': '6114065ab4a1fb0f7ddbb076ca34c7c702ec04ee8cc9b36fadcdac5efed58719',
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
        seg = seg.replace("tp4-mtp1-4352-ple-only-a118", "tp4-mtp1-4352-ple-only-a119")
        seg = seg.replace("attempt118", "attempt119").replace("19790", "19791")
        seg = seg.replace("ATTEMPT=118", "ATTEMPT=119").replace("a118", "a119").replace("A118", "A119")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19790" not in out and "attempt118" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A119_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a119-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a119" in derived and NEW_HEAD in derived and OLD_HEAD not in derived
    assert "ATTEMPT=119 PORT=19791" in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a118-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a119-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a119-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a119-fullgraphdet-w13n32.sh", "run-q38-a119-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
