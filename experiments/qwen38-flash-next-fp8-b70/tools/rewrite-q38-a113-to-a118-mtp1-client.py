#!/usr/bin/env python3
"""Create the A118 promotion packet from frozen A113: the first frozen MTP1 client (A114/A116 retired: resolver head pin, then a size-1 dispatch requirement that MTP1 never meets).

A113 is the full-decode-graph MTP1 identity (capture sizes [1, 2], KV
376569856 bytes) with the three exact-verify flags (serial GDN verifier rows,
row-wise TP all-reduce, row-wise hyperconnection norm) on overlay 1b2a17c1.
A118 keeps that launcher, supervisor and host wrapper and replaces the
inherited MTP0 client with one whose identity receipts, live-environment
checks and runtime verifier (A118, capture [1, 2], size-1 and size-2 FULL
dispatch receipts) describe the MTP1 line, while the output pins (short,
16-repeat, exact-2K, exact-4K) stay the MTP0 authorities. Attempt 114 /
port 19790.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A118_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh': '05b425212767762eca8895345d17437181f1699db47a61bc044575c02f6e06b5',
    'run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh': '9d986973463a2878d6ab789a87e72071d47af90c38c31b668a9ac10a258672aa',
    'supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh': '3f8f2e1b60ac5b4be6572dbcfa2a8786468ed32efb3db2584efd7f906d1a015d',
    'run-q38-a113-host-controlled.sh': '205d0ec75825463c3751dc64a0d41ce80427cd8f1d9b0571f1254aeb0c4a01d4',
    'verify-q38-a118-fullgraph-runtime.py': '6c5c3ca9a3b93d0e6da6f2e6f93d66172920384e709f812e98cb34103fe52bf1',
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60"
OLD_VERIFIER_SHA = "a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8"
NEW_VERIFIER_SHA = SOURCES['verify-q38-a118-fullgraph-runtime.py']
OLD_COMP = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"compile_sizes":[],"cudagraph_num_of_warmups":1}'
NEW_COMP = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}'
FLAG_GREPS = '''grep -zFxq 'VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the serial GDN verifier-row selector\n' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise all-reduce selector\n' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise hyperconnection norm selector\n' >&2
  exit 1
}
'''

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a113", "tp4-mtp1-4352-ple-only-a118")
        seg = seg.replace("attempt113", "attempt118").replace("19785", "19790")
        seg = seg.replace("ATTEMPT=113", "ATTEMPT=118").replace("a113", "a118").replace("A113", "A118")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19785" not in out and "attempt113" not in out
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
    env = os.environ.copy(); env["Q38_A118_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a118-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a118" in derived, "derived lacks a118 base name"
    assert "ATTEMPT=118 PORT=19790" in launcher, "launcher lacks attempt/port exports"
    assert NEW_HEAD in derived, "derived lacks the new head"
    assert OLD_HEAD not in derived, "derived still carries the old head"
    for flag in ("export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1\n", "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2\n", "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2\n"):
        assert flag in derived, flag
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh"))
    client = replace_once(client, "verify-q38-a48-fullgraph-runtime.py", "verify-q38-a118-fullgraph-runtime.py")
    client = replace_once(client, "4f4942289f3853f0dec60b9fcd14c644ca300abaaa9d9fa2ea56135f4d9f9c52", "0bd36f13056d79924e7598bf8d844db3a5b8b35639737c0ef0b5af68cad14753")
    client = replace_once(client, "expected_runtime_verifier=" + OLD_VERIFIER_SHA, "expected_runtime_verifier=" + NEW_VERIFIER_SHA)
    client = replace_n(client, OLD_COMP, NEW_COMP, 2)
    client = replace_n(client, OLD_HEAD, NEW_HEAD, 3)
    client = replace_once(client, '[[ "$server_command" != *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {\n  printf \'FAIL: MTP or reasoning parser unexpectedly present\\n\' >&2\n',
                          '[[ "$server_command" == *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {\n  printf \'FAIL: MTP absent or reasoning parser present\\n\' >&2\n')
    client = replace_once(client, "  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=0 max_model_len=4352 max_num_batched_tokens=64' \\\n  'kv_cache_memory_bytes=134217728' 'kv_cache_layout=BLHNC' \\\n",
                          "  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=1 max_model_len=4352 max_num_batched_tokens=64' \\\n  'mtp_exact_recurrent=0' \\\n  'kv_cache_memory_bytes=376569856' 'kv_cache_layout=BLHNC' \\\n")
    client = replace_once(client, 'assert labels.get("kv_cache_memory_bytes") == "134217728", labels', 'assert labels.get("kv_cache_memory_bytes") == "376569856", labels')
    client = replace_once(client, '        "tp": 4, "ep": 4, "mtp": 0, "graph": "FULL_DECODE_ONLY",\n        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1],\n',
                          '        "tp": 4, "ep": 4, "mtp": 1, "graph": "FULL_DECODE_ONLY",\n        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1, 2],\n        "exact_verify_selectors": ["VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1", "VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2", "VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2"],\n')
    client = replace_once(client, '        "input_embedding": "device", "kv_cache_memory_bytes": 134217728,\n', '        "input_embedding": "device", "kv_cache_memory_bytes": 376569856,\n')
    client = replace_once(client, "grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' \"/proc/${server_pid}/environ\" || {\n  printf 'FAIL: live server lacks exact twoshots selector\\n' >&2\n  exit 1\n}\n",
                          "grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' \"/proc/${server_pid}/environ\" || {\n  printf 'FAIL: live server lacks exact twoshots selector\\n' >&2\n  exit 1\n}\n" + FLAG_GREPS)
    client = replace_once(client, "  .size_1_full_dispatch_count > 0 and (.collective_processes | length) >= 4 and\n", "  .size_1_full_dispatch_count > 0 and .size_2_full_dispatch_count > 0 and (.collective_processes | length) >= 4 and\n")
    client = replace_once(client, "  .schema_version == 2 and .compilation_mode == \"NONE\" and\n", "  .schema_version == 3 and .compilation_mode == \"NONE\" and\n")
    assert client.count(" MTP0 ") == 3, client.count(" MTP0 ")
    client = client.replace(" MTP0 ", " MTP1 ")
    assert "134217728" not in client and OLD_HEAD not in client and "mtp=0" not in client

    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a113-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp1-4352-ple-only-a113-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a118-fullgraphdet-w13n32.sh", "run-q38-a118-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
