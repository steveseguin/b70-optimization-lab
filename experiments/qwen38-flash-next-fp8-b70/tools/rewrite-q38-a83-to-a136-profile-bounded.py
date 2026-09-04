#!/usr/bin/env python3
"""Create the A136 bounded torch-profiler packet (12 decode iterations after the 2K prefill) from frozen A83 (eager MTP1, serial GDN verifier rows, row-wise TP all-reduce and row-wise HC norm, per-step timing log, no trace).

Eager deterministic identity at 4352 tokens from the NVMe copy with the
Q38 repeatability trace armed on every rank for the first forward whose
maximum position reaches 2048 (the first verification step after prefill,
where the exact-recurrent MTP1 line diverges from the MTP0 line). The trace
records every decoder layer's output with per-row digests plus layer 0's
inner GDN records (in_proj, core, norm, out_proj) via
Q38_REPEATABILITY_TRACE_GDN_LAYERS=0 (overlay 8ca2cbc2). Attempt 136 / port 19807.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A136_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh': '10b794de42d9210def42ba3fd86f1c8a53bf82d7f77ab5c1aab24cc70c8b8cfb', 'run-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32-client.sh': '47f3b1160e38e35aac00299a79f5f3491a938758f88d3fd2cd8064279aa7cfbc', 'supervise-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh': '757a0a168daab806202dfa097221e95e2204a36224065a6bd2d6ea5bfd772063', 'run-q38-a83-host-controlled.sh': '9f182538adca15666c6ffd7649ffdfb4196bc9e95913c2b2b961ec4c530ce9e9'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
MTP0 = False
EXACT = False
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "5915cb0e88b03d709d743020d74c821c5b5b3ecf"
MTP_RULE = '$0 == "[[ \\"${mtp}\\" == \\"0\\" ]] || {" {\n  print "[[ \\"${mtp}\\" == \\"1\\" ]] || {"\n  next\n}\n'
EXACT_RULE = '$0 == "[[ \\"${mtp_exact}\\" == \\"0\\" ]] || {" {\n  print "[[ \\"${mtp_exact}\\" == \\"1\\" ]] || {"\n  next\n}\n'
MTP_GREPS = 'grep -Fxq \'[[ "${mtp}" == "1" ]] || {\' "$derived"\n! grep -Fq \'[[ "${mtp}" == "0" ]] || {\' "$derived"\n'
TRACE = 'export Q38_STEP_TIMING_LOG=10\n'

PROFILE_RULE = '$0 == "  --max-num-seqs 1" {\n  print\n  print "  --profiler-config \'\\\'\'{\\"profiler\\":\\"torch\\",\\"torch_profiler_dir\\":\\"/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp1-4352-ple-only-r1-attempt136/torch-profile\\",\\"torch_profiler_with_stack\\":false,\\"torch_profiler_use_gzip\\":true,\\"delay_iterations\\":34,\\"max_iterations\\":12}\'\\\'\'"\n  next\n}\n'
MTP_ANCHOR = '$0 == "[[ \\"${mtp}\\" == \\"0\\" ]] || {" {\n'

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a83", "tp4-mtp1-4352-ple-only-a136")
        seg = seg.replace("q38-mtp1-ple-only", "q38-mtp1-ple-only")
        seg = seg.replace("attempt83", "attempt136").replace("19755", "19807")
        seg = seg.replace("ATTEMPT=83", "ATTEMPT=136").replace("a83", "a136").replace("A83", "A136")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19755" not in out and "attempt83" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = replace_once(launcher, MTP_ANCHOR, PROFILE_RULE + MTP_ANCHOR)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    if MTP0:
        launcher = replace_once(launcher, MTP_RULE, "")
        launcher = replace_once(launcher, MTP_GREPS, "")
        launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=136 PORT=19807\n", "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=136 PORT=19807\n")
        launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=134217728\n" + TRACE)
    elif not EXACT:
        launcher = replace_once(launcher, '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n', '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n  print "export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1"\n  print "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2"\n  print "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2"\n')
        launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\n" + TRACE)
    else:
        launcher = replace_once(launcher, MTP_RULE, EXACT_RULE + MTP_RULE)
        launcher = replace_once(launcher, MTP_GREPS, MTP_GREPS + """grep -Fxq '[[ "${mtp_exact}" == "1" ]] || {' "$derived"\n""")
        launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=136 PORT=19807\n", "export MTP=1 MTP_EXACT=1 MAX_MODEL_LEN=4352 ATTEMPT=136 PORT=19807\n")
        launcher = replace_once(launcher, "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70\n", "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70\n")
        launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\n" + TRACE)
    env = os.environ.copy(); env["Q38_A136_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a136-base.sh").unlink(missing_ok=True)
    assert "--profiler-config" in derived and "torch-profile" in derived
    assert "q38-ple2k-a136" in derived and "  --enforce-eager\n" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    if MTP0:
        assert '[[ "${mtp}" == "0" ]] || {' in derived
    elif not EXACT:
        assert '[[ "${mtp}" == "1" ]] || {' in derived and "export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1\n" in derived and "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2\n" in derived and "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2\n" in derived
        assert "export MTP=1 MTP_EXACT=0 " in launcher
    else:
        assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp_exact}" == "1" ]] || {' in derived
        assert "runtime-stage-mtp1-exact-loadable.sha256" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh"))
    if MTP0:
        supervisor = replace_once(supervisor, ".identity.mtp == 1 and", ".identity.mtp == 0 and")
        supervisor = replace_once(supervisor, ".identity.kv_cache_memory_bytes == 376569856 and", ".identity.kv_cache_memory_bytes == 134217728 and")
    elif EXACT:
        supervisor = replace_once(supervisor, '.identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and', '.identity.stage_build_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and')
    supervisor = replace_once(supervisor, "expected_wrapper=10b794de42d9210def42ba3fd86f1c8a53bf82d7f77ab5c1aab24cc70c8b8cfb", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=47f3b1160e38e35aac00299a79f5f3491a938758f88d3fd2cd8064279aa7cfbc", "expected_client=" + digest(client))
    host = successor(source("run-q38-a83-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=757a0a168daab806202dfa097221e95e2204a36224065a6bd2d6ea5bfd772063", "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp1-4352-ple-only-a136-mkldnndet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a136-mkldnndet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a136-mkldnndet-w13n32.sh", "run-q38-a136-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
