#!/usr/bin/env python3
"""Create the A133 packet from frozen A113: the MTP2 twin of the graph MTP1 battery.

Same deterministic full-decode-graph identity and the three exact-verify
selectors, with two speculative tokens: `num_speculative_tokens` 2, capture
sizes [1, 2, 3], row-wise selectors at max rows 3 (the serial GDN path
handles any number of verifier rows), KV budget unchanged, step-timing
hook on. Attempt 133 / port 19804, overlay 5915cb0e.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A133_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh': '05b425212767762eca8895345d17437181f1699db47a61bc044575c02f6e06b5', 'run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh': '9d986973463a2878d6ab789a87e72071d47af90c38c31b668a9ac10a258672aa', 'supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh': '3f8f2e1b60ac5b4be6572dbcfa2a8786468ed32efb3db2584efd7f906d1a015d', 'run-q38-a113-host-controlled.sh': '205d0ec75825463c3751dc64a0d41ce80427cd8f1d9b0571f1254aeb0c4a01d4'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_HEAD = "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60"
NEW_HEAD = "5915cb0e88b03d709d743020d74c821c5b5b3ecf"

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a113", "tp4-mtp2-4352-ple-only-a133")
        seg = seg.replace("fullgraphdet-mtp1-4352-ple-only", "fullgraphdet-mtp2-4352-ple-only")
        seg = seg.replace("q38-mtp1-ple-only-a113", "q38-mtp2-ple-only-a133")
        seg = seg.replace("attempt113", "attempt133").replace("19785", "19804")
        seg = seg.replace("ATTEMPT=113", "ATTEMPT=133").replace("a113", "a133").replace("A113", "A133")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19785" not in out and "attempt113" not in out and "mtp1-4352" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = replace_once(launcher, '  print "[[ \\"${mtp}\\" == \\"1\\" ]] || {"\n', '  print "[[ \\"${mtp}\\" == \\"2\\" ]] || {"\n')
    launcher = replace_once(launcher, '  print "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2"\n', '  print "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3"\n')
    launcher = replace_once(launcher, '  print "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2"\n', '  print "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3"\n')
    launcher = replace_once(launcher, "cudagraph_capture_sizes'\\'': [1, 2],\"", "cudagraph_capture_sizes'\\'': [1, 2, 3],\"")
    launcher = replace_once(launcher, "max_cudagraph_capture_size'\\'': 2, '\\''compile_sizes'\\'': [],\"", "max_cudagraph_capture_size'\\'': 3, '\\''compile_sizes'\\'': [],\"")
    launcher = replace_once(launcher, "cudagraph_capture_sizes == [1, 2]\"", "cudagraph_capture_sizes == [1, 2, 3]\"")
    launcher = replace_once(launcher, "max_cudagraph_capture_size == 2\"", "max_cudagraph_capture_size == 3\"")
    launcher = replace_n(launcher, '\\"cudagraph_capture_sizes\\":[1,2],\\"max_cudagraph_capture_size\\":2,', '\\"cudagraph_capture_sizes\\":[1,2,3],\\"max_cudagraph_capture_size\\":3,', 2)
    launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=133 PORT=19804\n", "export MTP=2 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=133 PORT=19804\n")
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\nexport Q38_STEP_TIMING_LOG=10\n")
    grep_old = 'grep -Fxq \'[[ "${mtp}" == "1" ]] || {\' "$derived"\n'
    if launcher.count(grep_old) == 1:
        launcher = launcher.replace(grep_old, 'grep -Fxq \'[[ "${mtp}" == "2" ]] || {\' "$derived"\n')
    env = os.environ.copy(); env["Q38_A133_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a133-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a133" in derived and NEW_HEAD in derived and OLD_HEAD not in derived
    assert '[[ "${mtp}" == "2" ]] || {' in derived
    assert "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3\n" in derived and "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3\n" in derived
    assert "cudagraph_capture_sizes == [1, 2, 3]" in derived and '"cudagraph_capture_sizes":[1,2,3]' in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, ".identity.mtp == 1 and", ".identity.mtp == 2 and")
    supervisor = replace_once(supervisor, ".identity.cudagraph_capture_sizes == [1,2] and", ".identity.cudagraph_capture_sizes == [1,2,3] and")
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a113-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh", "run-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh", "run-q38-a133-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
