#!/usr/bin/env python3
"""Create the A205 packet from frozen A120: byte-identical apart from attempt, port and state names (graph MTP1 (PLE-only placement) with cold routed experts host-resident through the per-expert offset table (Q38_EXPERT_HOST_PLACEMENT), USB checkpoint, overlay 68a410ba4031, Q38_STEP_TIMING_LOG + Q38_MEM_NOTE)."""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A205_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': 'cc205ce58baf7d1ae9a51df42b2c50b4ee86d4bfabcb957a6a24ef0eea0d2714', 'run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh': '4c25729665b793e5a563cec1594cbaf9693e38c4dfb90fd7c3452b7938034d61', 'supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': '251331ec735c7e2600dd240959453e646f8d781c88bbafed95da7b0b74eacd90', 'run-q38-a120-host-controlled.sh': 'ca3ad0dc8787db77abdf9c8398646b35d9bd96a9390d43654945d6d3df9321d4'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a120", "tp4-mtp1-4352-ple-only-a205")
        seg = seg.replace("attempt120", "attempt205").replace("19792", "19875")
        seg = seg.replace("ATTEMPT=120", "ATTEMPT=205").replace("a120", "a205").replace("A120", "A205")
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
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)

OLD_HEAD = "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60"
NEW_HEAD = "9959914b57e425b70697cabe004a281d4f4f9ecc"
def patch_a205_launcher(l):
    assert l.count(OLD_HEAD) == 2, l.count(OLD_HEAD); l = l.replace(OLD_HEAD, NEW_HEAD)
    l = replace_once(l, "export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8\n", "export MODEL_PATH=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\n")
    l = replace_once(l, "export KV_CACHE_MEMORY_BYTES=", "export Q38_STEP_TIMING_LOG=10\nexport Q38_MEM_NOTE=1\nexport Q38_EXPERT_HOST_PLACEMENT=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260905-q38-expert-host-placement-2gib-per-rank.json\nexport KV_CACHE_MEMORY_BYTES=")
    return l
def patch_a205_supervisor(sv):
    return replace_once(sv, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
def patch_a205_client(c):
    assert c.count(OLD_HEAD) >= 1; c = c.replace(OLD_HEAD, NEW_HEAD)
    return replace_once(c, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')

def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = patch_a205_launcher(launcher)
    env = os.environ.copy(); env["Q38_A205_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a205-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a205" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh"))
    client = patch_a205_client(client)
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"))
    supervisor = patch_a205_supervisor(supervisor)
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a120-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp1-4352-ple-only-a205-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a205-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a205-fullgraphdet-w13n32.sh", "run-q38-a205-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
