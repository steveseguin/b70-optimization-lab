#!/usr/bin/env python3
"""Create the A197 step and per-layer timing packet from frozen A83 (eager MTP0 twin of A122 with the per-step timing log, no trace).

Eager deterministic identity at 4352 tokens from the NVMe copy with the
Q38 repeatability trace armed on every rank for the first forward whose
maximum position reaches 2048 (the first verification step after prefill,
where the exact-recurrent MTP1 line diverges from the MTP0 line). The trace
records every decoder layer's output with per-row digests (overlay
d132de8c). Attempt 163 / port 19868.
"""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import q38_freeze_mitigation as _fm
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A197_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh': '10b794de42d9210def42ba3fd86f1c8a53bf82d7f77ab5c1aab24cc70c8b8cfb', 'run-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32-client.sh': '47f3b1160e38e35aac00299a79f5f3491a938758f88d3fd2cd8064279aa7cfbc', 'supervise-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh': '757a0a168daab806202dfa097221e95e2204a36224065a6bd2d6ea5bfd772063', 'run-q38-a83-host-controlled.sh': '9f182538adca15666c6ffd7649ffdfb4196bc9e95913c2b2b961ec4c530ce9e9'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
MTP0 = True
EXACT = False
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "08df70ea5a8e9f6c7112701c968aaf9a775ff0df"
MTP_RULE = '$0 == "[[ \\"${mtp}\\" == \\"0\\" ]] || {" {\n  print "[[ \\"${mtp}\\" == \\"1\\" ]] || {"\n  next\n}\n'
EXACT_RULE = '$0 == "[[ \\"${mtp_exact}\\" == \\"0\\" ]] || {" {\n  print "[[ \\"${mtp_exact}\\" == \\"1\\" ]] || {"\n  next\n}\n'
MTP_GREPS = 'grep -Fxq \'[[ "${mtp}" == "1" ]] || {\' "$derived"\n! grep -Fq \'[[ "${mtp}" == "0" ]] || {\' "$derived"\n'
TRACE = 'export Q38_STEP_TIMING_LOG=10\nexport Q38_MEM_NOTE=1\nexport Q38_DUMP_TOPK=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/q38-dumps/a197\nexport Q38_DUMP_TOPK_MAX=250000\n'

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a83", "tp4-mtp0-4352-ple-only-a197")
        seg = seg.replace("mkldnndet-mtp1-4352-ple-only", "mkldnndet-mtp0-4352-ple-only")
        seg = seg.replace("q38-mtp1-ple-only", "q38-mtp0-ple-only")
        seg = seg.replace("attempt83", "attempt197").replace("19755", "19868")
        seg = seg.replace("ATTEMPT=83", "ATTEMPT=197").replace("a83", "a197").replace("A83", "A197")
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
PARAMS4_PY = "'ple_embedding.ngram_embedding.weight', 'embed_tokens.weight', 'mlp.experts'"
PARAMS4_CSV = "ple_embedding.ngram_embedding.weight,embed_tokens.weight,mlp.experts"
PARAMS4_SP = "ple_embedding.ngram_embedding.weight embed_tokens.weight mlp.experts"
SQ = "'\\''"  # how a single quote is spelled inside the launcher's single-quoted awk program
def q(t):
    return t.replace("'", SQ)
def patch_a177(l):
    l = replace_once(l, '  print substr($0, 1, RLENGTH) "' + q("'ple_embedding.ngram_embedding.weight',") + '"\n', '  print substr($0, 1, RLENGTH) "' + q(PARAMS4_PY) + '"\n')
    l = replace_once(l, '$0 == "embed_selector = ' + q("'embed_tokens.weight'") + '" { next }\n', '')
    l = replace_once(l, 'index($0, "assert f' + q("'.{embed_selector}.'") + '") == 1 { next }\n', '')
    l = replace_once(l, '$0 == "print(f' + q("'embed_bytes_per_rank={embed_bytes_per_rank}'") + ')" { next }\n', '')
    l = replace_once(l, '$0 == "embed_bytes_per_rank = 317_849_600" { next }\n', '$0 == "embed_bytes_per_rank = 317_849_600" {\n  print\n  print "experts_bytes_per_rank = 2 * (128 * 1280 * 2560 + 128 * 2560 * 640)"\n  next\n}\n')
    l = replace_once(l, '  print "offload_bytes_per_rank = ple_bytes_per_rank"\n', '  print "offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank + experts_bytes_per_rank"\n')
    l = l.replace('_selective_ple_only_uva', '_selective_ple_embed_experts_budget13p4_uva')
    l = replace_once(l, 'gsub(/12\\.25/, "12.0")', 'gsub(/12\\.25/, "13.4")')
    l = replace_once(l, 'gsub(/12\\.22/, "11.92")', 'gsub(/12\\.22/, "13.78")')
    l = replace_once(l, 'gsub(/exact_12\\.22/, "exact_11.92")', 'gsub(/exact_12\\.22/, "exact_13.78")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "' + PARAMS4_CSV + '")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "' + PARAMS4_SP + '")')
    l = replace_once(l, "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=12.0,' \"$derived\"\n", "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=13.4,' \"$derived\"\n")
    l = replace_once(l, 'grep -Fxq "        \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "        ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, 'grep -Fxq "    \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "    ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank' \"$derived\"\n", "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank + experts_bytes_per_rank' \"$derived\"\ngrep -Fxq 'experts_bytes_per_rank = 2 * (128 * 1280 * 2560 + 128 * 2560 * 640)' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq 'offload_budget = int(12.0 * 1024**3)' \"$derived\"\n", "grep -Fxq 'offload_budget = int(13.4 * 1024**3)' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-gb 12.0' \"$derived\"\n", "grep -Fxq '  --cpu-offload-gb 13.4' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-params ple_embedding.ngram_embedding.weight' \"$derived\"\n", "grep -Fxq '  --cpu-offload-params " + PARAMS4_SP + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_gb=12.0\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_gb=13.4\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_params=ple_embedding.ngram_embedding.weight\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_params=" + PARAMS4_CSV + "\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, '! grep -Fq "\'embed_tokens.weight\'" "$derived"\n', 'grep -Fq "\'mlp.experts\'" "$derived"\n')
    return l
def patch_client(c):
    return replace_once(c, "'cpu_offload_gb=12.0' 'cpu_offload_params=ple_embedding.ngram_embedding.weight'", "'cpu_offload_gb=13.4' 'cpu_offload_params=" + PARAMS4_CSV + "'")

def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = _fm.patch_launcher(launcher)
    if MTP0:
        launcher = replace_once(launcher, MTP_RULE, "")
        launcher = replace_once(launcher, MTP_GREPS, "")
        launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=197 PORT=19868\n", "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=197 PORT=19868\n")
        launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=134217728\n" + TRACE)
    else:
        launcher = replace_once(launcher, MTP_RULE, EXACT_RULE + MTP_RULE)
        launcher = replace_once(launcher, MTP_GREPS, MTP_GREPS + """grep -Fxq '[[ "${mtp_exact}" == "1" ]] || {' "$derived"\n""")
        launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=197 PORT=19868\n", "export MTP=1 MTP_EXACT=1 MAX_MODEL_LEN=4352 ATTEMPT=197 PORT=19868\n")
        launcher = replace_once(launcher, "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70\n", "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70\n")
        launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\n" + TRACE)
    launcher = patch_a177(launcher)
    env = os.environ.copy(); env["Q38_A197_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a197-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a197" in derived and "  --enforce-eager\n" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    if MTP0:
        assert '[[ "${mtp}" == "0" ]] || {' in derived
    else:
        assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp_exact}" == "1" ]] || {' in derived
        assert "runtime-stage-mtp1-exact-loadable.sha256" in derived
    launcher = replace_once(launcher, "export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8\n", "export MODEL_PATH=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\n")
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32-client.sh"))
    client = patch_client(c := client) if False else patch_client(client)
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh"))
    XPU_OLD = '  timeout 30s xpu-smi discovery -j >"${evidence_dir}/xpu-discovery.json" \\\n    2>"${evidence_dir}/xpu-discovery.err" || true\n  for device in 0 1 2 3; do\n    timeout 30s xpu-smi stats -d "$device" -j \\\n      >"${evidence_dir}/xpu-stats-${device}.json" \\\n      2>"${evidence_dir}/xpu-stats-${device}.err" || true\n  done\n'
    XPU_NEW = '  # Freeze mitigation (2026-09-05): xpu-smi (Intel MEI telemetry) was the last journal entry\n  # before five of six silent host freezes; receipts are copied from attempt 146 instead.\n  xpu_ref=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/xpu-receipts-reference\n  cp -- "${xpu_ref}/xpu-discovery.json" "${evidence_dir}/xpu-discovery.json"\n  printf \'bypassed: cached receipt from attempt 146\\n\' >"${evidence_dir}/xpu-discovery.err"\n  for device in 0 1 2 3; do\n    cp -- "${xpu_ref}/xpu-stats-${device}.json" "${evidence_dir}/xpu-stats-${device}.json"\n    printf \'bypassed: cached receipt from attempt 146\\n\' >"${evidence_dir}/xpu-stats-${device}.err"\n  done\n'
    supervisor = replace_once(supervisor, XPU_OLD, XPU_NEW)
    supervisor = replace_once(supervisor, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
    if MTP0:
        supervisor = replace_once(supervisor, ".identity.mtp == 1 and", ".identity.mtp == 0 and")
        supervisor = replace_once(supervisor, ".identity.kv_cache_memory_bytes == 376569856 and", ".identity.kv_cache_memory_bytes == 134217728 and")
    else:
        supervisor = replace_once(supervisor, '.identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and', '.identity.stage_build_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and')
    supervisor = replace_once(supervisor, "expected_wrapper=10b794de42d9210def42ba3fd86f1c8a53bf82d7f77ab5c1aab24cc70c8b8cfb", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=47f3b1160e38e35aac00299a79f5f3491a938758f88d3fd2cd8064279aa7cfbc", "expected_client=" + digest(client))
    host = successor(source("run-q38-a83-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=757a0a168daab806202dfa097221e95e2204a36224065a6bd2d6ea5bfd772063", "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp0-4352-ple-only-a197-mkldnndet-w13n32.sh", "run-tp4-mtp0-4352-ple-only-a197-mkldnndet-w13n32-client.sh", "supervise-tp4-mtp0-4352-ple-only-a197-mkldnndet-w13n32.sh", "run-q38-a197-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
