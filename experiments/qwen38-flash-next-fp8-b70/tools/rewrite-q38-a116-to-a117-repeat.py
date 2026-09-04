#!/usr/bin/env python3
"""Create the A117 packet from frozen A116: the byte-identical fresh-server repeat of the MTP1 promotion candidate.

A117 keeps every A116 file unchanged apart from the attempt number, port and
state names, so a second independently started server runs the same frozen
MTP1 client against the same pins. Attempt 115 / port 19789.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A117_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh': '9ccfa68bd3321a863be14473be354b127962240b12a2973cb27bb1763b599643',
    'run-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32-client.sh': 'f59b1cf0ae258d10e033667c13dcb40112fee899381cd0fed7a6c04ff4f31d0e',
    'supervise-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh': '4522ce0a163782d31acb40edef1075d9120b4b7d1e7fa3c092e2572af7d12f7b',
    'run-q38-a116-host-controlled.sh': '05d114ad54f822e691e20c8f63a312d1d9c57c13b762aa029da6b2e0da18be13',
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
        seg = seg.replace("tp4-mtp1-4352-ple-only-a116", "tp4-mtp1-4352-ple-only-a117")
        seg = seg.replace("attempt116", "attempt117").replace("19788", "19789")
        seg = seg.replace("ATTEMPT=116", "ATTEMPT=117").replace("a116", "a117").replace("A116", "A117")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19788" not in out and "attempt116" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A117_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a117-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a117" in derived and NEW_HEAD in derived and OLD_HEAD not in derived
    assert "ATTEMPT=117 PORT=19789" in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a116-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp1-4352-ple-only-a116-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a117-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a117-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a117-fullgraphdet-w13n32.sh", "run-q38-a117-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
