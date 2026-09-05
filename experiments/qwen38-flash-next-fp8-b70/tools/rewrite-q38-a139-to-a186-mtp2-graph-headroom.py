#!/usr/bin/env python3
"""Create the A186 packet from frozen A139: byte-identical apart from attempt, port and state names (graph MTP2 with VRAM headroom: USB checkpoint, overlay 08df70ea, UVA offload of embed_tokens + mlp.experts under a 13.4 GiB budget (expected 13.78 GiB), Q38_STEP_TIMING_LOG + Q38_MEM_NOTE)."""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A186_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh': '3e71022b085a70e29330d6b4f5493def1869b3dde9e7c91e7bc797a9dc8b1233', 'run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh': '12a046230a425e43d411853812d5acc7695ee4145153182e852e354ca5221432', 'supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh': '5185f96e57aa2f0db20b0595d66c5b060cf0fbf0325fa86783818f92b438dd1e', 'run-q38-a139-host-controlled.sh': 'def8537571afcf682457367ef83969e1df3e64775938c2549e1fc24f66cfd6b7'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp2-4352-ple-only-a139", "tp4-mtp2-4352-ple-only-a186")
        seg = seg.replace("attempt139", "attempt186").replace("19810", "19857")
        seg = seg.replace("ATTEMPT=139", "ATTEMPT=186").replace("a139", "a186").replace("A139", "A186")
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

OLD_HEAD = "5915cb0e88b03d709d743020d74c821c5b5b3ecf"
NEW_HEAD = "08df70ea5a8e9f6c7112701c968aaf9a775ff0df"
def patch_a186_launcher(l):
    assert l.count(OLD_HEAD) == 2, l.count(OLD_HEAD); l = l.replace(OLD_HEAD, NEW_HEAD)
    l = replace_once(l, "export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8\n", "export MODEL_PATH=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\n")
    l = replace_once(l, "export KV_CACHE_MEMORY_BYTES=", "export Q38_STEP_TIMING_LOG=10\nexport Q38_MEM_NOTE=1\nexport KV_CACHE_MEMORY_BYTES=")
    return patch_a177(l)
def patch_a186_supervisor(sv):
    return replace_once(sv, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
def patch_a186_client(c):
    assert c.count(OLD_HEAD) >= 1; c = c.replace(OLD_HEAD, NEW_HEAD)
    c = replace_once(c, '*"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"*', '*"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"*')
    return patch_client(c)

def main():
    launcher = source("launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = patch_a186_launcher(launcher)
    env = os.environ.copy(); env["Q38_A186_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a186-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a186" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh"))
    client = patch_a186_client(client)
    supervisor = successor(source("supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"))
    supervisor = patch_a186_supervisor(supervisor)
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a139-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp2-4352-ple-only-a186-fullgraphdet-w13n32.sh", "run-tp4-mtp2-4352-ple-only-a186-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp2-4352-ple-only-a186-fullgraphdet-w13n32.sh", "run-q38-a186-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
