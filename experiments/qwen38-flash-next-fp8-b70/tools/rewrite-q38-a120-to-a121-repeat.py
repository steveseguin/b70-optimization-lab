#!/usr/bin/env python3
"""Create the A121 packet from frozen A120: the byte-identical fresh-server repeat of the MTP1 promotion candidate.

A121 keeps every A120 file unchanged apart from the attempt number, port and
state names, so a second independently started server runs the same frozen
MTP1 client against the same pins. Attempt 115 / port 19793.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A121_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': 'cc205ce58baf7d1ae9a51df42b2c50b4ee86d4bfabcb957a6a24ef0eea0d2714',
    'run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh': '4c25729665b793e5a563cec1594cbaf9693e38c4dfb90fd7c3452b7938034d61',
    'supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': '251331ec735c7e2600dd240959453e646f8d781c88bbafed95da7b0b74eacd90',
    'run-q38-a120-host-controlled.sh': 'ca3ad0dc8787db77abdf9c8398646b35d9bd96a9390d43654945d6d3df9321d4',
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
        seg = seg.replace("tp4-mtp1-4352-ple-only-a120", "tp4-mtp1-4352-ple-only-a121")
        seg = seg.replace("attempt120", "attempt121").replace("19792", "19793")
        seg = seg.replace("ATTEMPT=120", "ATTEMPT=121").replace("a120", "a121").replace("A120", "A121")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19792" not in out and "attempt120" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A121_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a121-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a121" in derived and NEW_HEAD in derived and OLD_HEAD not in derived
    assert "ATTEMPT=121 PORT=19793" in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a120-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a121-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a121-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a121-fullgraphdet-w13n32.sh", "run-q38-a121-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
