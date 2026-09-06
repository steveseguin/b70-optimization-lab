#!/usr/bin/env python3
"""Create the A226 packet from frozen A120 (MTP1) for the A213 identity: PLE + embeddings offloaded at 12.25 (12.22 GiB), hot experts resident, never-hit experts host-placed at load time (/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json) on clean head 005dc5789589; realistic suite (LocalMaxxing metric)."""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A226_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': 'cc205ce58baf7d1ae9a51df42b2c50b4ee86d4bfabcb957a6a24ef0eea0d2714', 'run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh': '4c25729665b793e5a563cec1594cbaf9693e38c4dfb90fd7c3452b7938034d61', 'supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh': '251331ec735c7e2600dd240959453e646f8d781c88bbafed95da7b0b74eacd90', 'run-q38-a120-host-controlled.sh': 'ca3ad0dc8787db77abdf9c8398646b35d9bd96a9390d43654945d6d3df9321d4'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a120", "tp4-mtp1-4352-ple-only-a226")
        seg = seg.replace("attempt120", "attempt226").replace("19792", "19896")
        seg = seg.replace("ATTEMPT=120", "ATTEMPT=226").replace("a120", "a226").replace("A120", "A226")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19792" not in out and "attempt120" not in out
    return out
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), a[:80]); return t.replace(a, b)
def replace_once(t, a, b):
    assert t.count(a) == 1, (t.count(a), a[:80]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
PARAMS4_PY = "'ple_embedding.ngram_embedding.weight', 'embed_tokens.weight'"
PARAMS4_CSV = "ple_embedding.ngram_embedding.weight,embed_tokens.weight"
PARAMS4_SP = "ple_embedding.ngram_embedding.weight embed_tokens.weight"
SQ = "'\\''"  # how a single quote is spelled inside the launcher's single-quoted awk program
def q(t):
    return t.replace("'", SQ)
def patch_a177(l):
    l = replace_once(l, '  print substr($0, 1, RLENGTH) "' + q("'ple_embedding.ngram_embedding.weight',") + '"\n', '  print substr($0, 1, RLENGTH) "' + q(PARAMS4_PY) + '"\n')
    l = replace_once(l, '$0 == "embed_selector = ' + q("'embed_tokens.weight'") + '" { next }\n', '')
    l = replace_once(l, 'index($0, "assert f' + q("'.{embed_selector}.'") + '") == 1 { next }\n', '')
    l = replace_once(l, '$0 == "print(f' + q("'embed_bytes_per_rank={embed_bytes_per_rank}'") + ')" { next }\n', '')
    l = replace_once(l, '$0 == "embed_bytes_per_rank = 317_849_600" { next }\n', '$0 == "embed_bytes_per_rank = 317_849_600" {\n  print\n  next\n}\n')
    l = replace_once(l, '  print "offload_bytes_per_rank = ple_bytes_per_rank"\n', '  print "offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank"\n')
    l = l.replace('_selective_ple_only_uva', '_selective_ple_embed_budget12p25_uva')
    l = replace_once(l, 'gsub(/12\\.25/, "12.0")', 'gsub(/12\\.25/, "12.25")')
    l = replace_once(l, 'gsub(/12\\.22/, "11.92")', 'gsub(/12\\.22/, "12.22")')
    l = replace_once(l, 'gsub(/exact_12\\.22/, "exact_11.92")', 'gsub(/exact_12\\.22/, "exact_12.22")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "' + PARAMS4_CSV + '")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "' + PARAMS4_SP + '")')
    l = replace_once(l, "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=12.0,' \"$derived\"\n", "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=12.25,' \"$derived\"\n")
    l = replace_once(l, 'grep -Fxq "        \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "        ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, 'grep -Fxq "    \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "    ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank' \"$derived\"\n", "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq 'offload_budget = int(12.0 * 1024**3)' \"$derived\"\n", "grep -Fxq 'offload_budget = int(12.25 * 1024**3)' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-gb 12.0' \"$derived\"\n", "grep -Fxq '  --cpu-offload-gb 12.25' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-params ple_embedding.ngram_embedding.weight' \"$derived\"\n", "grep -Fxq '  --cpu-offload-params " + PARAMS4_SP + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_gb=12.0\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_gb=12.25\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_params=ple_embedding.ngram_embedding.weight\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_params=" + PARAMS4_CSV + "\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, '! grep -Fq "\'embed_tokens.weight\'" "$derived"\n', 'grep -Fq "\'embed_tokens.weight\'" "$derived"\n')
    l = replace_once(l, "! grep -Fq -- '--cpu-offload-gb 12.25' \"$derived\"\n", "grep -Fq -- '--cpu-offload-gb 12.25' \"$derived\"\n")
    l = replace_once(l, "! grep -Fq 'exact_12.22' \"$derived\"\n", "grep -Fq 'exact_12.22' \"$derived\"\n")
    return l
def patch_client(c):
    return replace_once(c, "'cpu_offload_gb=12.0' 'cpu_offload_params=ple_embedding.ngram_embedding.weight'", "'cpu_offload_gb=12.25' 'cpu_offload_params=" + PARAMS4_CSV + "'")

OLD_HEAD = "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60"
NEW_HEAD = "005dc57895896f770157ea94f68e473e7447139e"  # q38-placement-mtp1-clean: lossless MTP1 head + table kernel + load-time never-hit expert placement
def patch_a226_launcher(l):
    assert l.count(OLD_HEAD) == 2, l.count(OLD_HEAD)
    l = replace_once(l, "export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8\n", "export MODEL_PATH=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\n")
    return patch_a177(l)
def patch_a226_supervisor(sv):
    return replace_once(sv, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
def patch_a226_client(c):
    assert c.count(OLD_HEAD) >= 1
    c = replace_once(c, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
    return patch_client(c)

def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = patch_a226_launcher(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\nexport Q38_EXPERT_HOST_PLACEMENT=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json\n")
    env = os.environ.copy(); env["Q38_A226_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a226-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a226" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh"))
    client = replace_once(client, '"placement": "ple_only_uva", "ple_host_bytes_per_rank": 12800061440,', '"placement": "ple_embed_budget12p25_uva_cold_expert_host_placement", "ple_host_bytes_per_rank": 12800061440, "host_offload_bytes_per_rank": 13117911040, "host_offload_params": "ple_embedding.ngram_embedding.weight,embed_tokens.weight", "expert_host_placement": "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json",')
    client = patch_a226_client(client)
    client = client.replace(OLD_HEAD, NEW_HEAD)
    client = client.replace("0bd36f13056d79924e7598bf8d844db3a5b8b35639737c0ef0b5af68cad14753", "13073e712ba4743cd0da1d43e4eddc4d7a246b5eda28cdff0ba9f9999243cef0").replace("4f4942289f3853f0dec60b9fcd14c644ca300abaaa9d9fa2ea56135f4d9f9c52", "13073e712ba4743cd0da1d43e4eddc4d7a246b5eda28cdff0ba9f9999243cef0")
    assert client.count("13073e712ba4743cd0da1d43e4eddc4d7a246b5eda28cdff0ba9f9999243cef0") >= 1
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"))
    supervisor = patch_a226_supervisor(supervisor)
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a120-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32.sh", "run-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32.sh", "run-q38-a226-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
