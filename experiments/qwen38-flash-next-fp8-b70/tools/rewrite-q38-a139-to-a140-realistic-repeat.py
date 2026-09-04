#!/usr/bin/env python3
"""Create the A140 packet from frozen A139: byte-identical apart from attempt, port and state names (realistic-suite run of the same identity)."""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A140_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh': '3e71022b085a70e29330d6b4f5493def1869b3dde9e7c91e7bc797a9dc8b1233', 'run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh': '12a046230a425e43d411853812d5acc7695ee4145153182e852e354ca5221432', 'supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh': '5185f96e57aa2f0db20b0595d66c5b060cf0fbf0325fa86783818f92b438dd1e', 'run-q38-a139-host-controlled.sh': 'def8537571afcf682457367ef83969e1df3e64775938c2549e1fc24f66cfd6b7'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp2-4352-ple-only-a139", "tp4-mtp2-4352-ple-only-a140")
        seg = seg.replace("attempt139", "attempt140").replace("19810", "19811")
        seg = seg.replace("ATTEMPT=139", "ATTEMPT=140").replace("a139", "a140").replace("A139", "A140")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19810" not in out and "attempt139" not in out
    return out
def replace_once(t, a, b):
    assert t.count(a) == 1, (t.count(a), a[:80]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
def main():
    launcher = source("launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A140_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a140-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a140" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a139-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp2-4352-ple-only-a140-fullgraphdet-w13n32.sh", "run-tp4-mtp2-4352-ple-only-a140-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp2-4352-ple-only-a140-fullgraphdet-w13n32.sh", "run-q38-a140-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
