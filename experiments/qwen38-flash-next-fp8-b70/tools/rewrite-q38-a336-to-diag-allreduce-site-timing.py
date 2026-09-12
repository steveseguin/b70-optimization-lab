#!/usr/bin/env python3
"""Derive a timing-diagnostic MTP0 packet from the frozen promoted A336 packet (W13-N64, graph,
placement): identical apart from attempt, port and state names, the overlay head (the diagnostic
head on the promoted line) and a block of Q38_* exports in the launcher.

usage: rewrite-q38-a336-to-diag-allreduce-site-timing.py <attempt> <port> <new_head> <extra_env...>
       Q38_REWRITE_VALIDATE_ONLY=1 ... re-checks an emitted packet byte for byte.
"""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
attempt, port, NEW_HEAD, *extra_env = sys.argv[1:]
assert re.fullmatch(r"[0-9a-f]{40}", NEW_HEAD)
VALIDATE_ONLY = os.environ.get("Q38_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh': 'cb48ec0507f78d618ee60d2dbb61a29ce027041fefd5b2cd292cf3458eba9240',
    'run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh': 'e681c5eaf4dbbfc4de37b1c848581ae9a01d8d1f900bd6eefdbdc9377844139a',
    'supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh': '7a923ecc2eea552ef7858897043d327e3a6380d89a76d793ed3d0aedd5ea76c8',
    'run-q38-a336-host-controlled.sh': '5c82156670f79f9368c613895d4bb022cd998b9a18999c4a03f9d9fcdc901543',
}
OLD_HEAD = "2a372e860e273273357cb7437ac7de1694304f9f"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp0-4352-ple-only-a336", f"tp4-mtp0-4352-ple-only-a{attempt}")
        seg = seg.replace("attempt336", f"attempt{attempt}").replace("19949", port)
        seg = seg.replace("ATTEMPT=336", f"ATTEMPT={attempt}").replace("a336", f"a{attempt}").replace("A336", f"A{attempt}")
        return seg
    parts, last = [], 0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last = m.end()
    parts.append(rename(text[last:])); out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    stripped = HASH_TOKEN.sub("", out)
    assert "19949" not in stripped and "attempt336" not in stripped and "a336" not in stripped
    return out
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:90]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
def main():
    launcher = source("launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_n(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0" * 64, 1)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    exports = "".join(f"export {kv}\n" for kv in extra_env)
    launcher = replace_n(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", "export KV_CACHE_MEMORY_BYTES=134217728\n" + exports, 1)
    env = os.environ.copy(); env[f"Q38_A{attempt}_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path(f"/tmp/q38-ple2k-a{attempt}-base.sh").unlink(missing_ok=True)
    assert f"q38-ple2k-a{attempt}" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh"))
    client = client.replace(OLD_HEAD, NEW_HEAD)
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"))
    supervisor = replace_n(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"], "expected_wrapper=" + digest(launcher), 1)
    supervisor = replace_n(supervisor, "expected_client=" + SOURCES["run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh"], "expected_client=" + digest(client), 1)
    host = successor(source("run-q38-a336-host-controlled.sh"))
    host = replace_n(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"], "expected_supervisor=" + digest(supervisor), 1)
    out_names = (
        f"launch-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64.sh",
        f"run-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64-client.sh",
        f"supervise-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64.sh",
        f"run-q38-a{attempt}-host-controlled.sh",
    )
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
