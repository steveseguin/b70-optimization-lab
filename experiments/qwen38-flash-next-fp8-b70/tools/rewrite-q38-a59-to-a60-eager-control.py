#!/usr/bin/env python3
"""Create the A60 no-graph control packet from frozen A59.

A60 keeps every A59 server identity (tuned M1 W13-N32 map, public oneCCL
with `twoshots`, external checkpoint, PLE-only UVA placement, 2304 max model
length, host guards, Torch trace) and removes only the full-decode graph: the
launcher rules that turned the eager base into the graph server are deleted,
so the derived launcher keeps the base's `--enforce-eager`, `XPU_GRAPH=0`,
and graph-disabled exports, and its identity receipts read
`eager=1 graph=none` and `diagnostics=nograph-public-oneccl-torch-trace`.
The campaign, run, cache, compile, and evidence names carry `nograph` instead
of `fullgraph` so nothing collides with the graph arms. Attempt 60 / port
19732. The frozen client is generated only for hash pins; the logprob probe
is the client.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A60_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh": "8e4ebce78bf5c0ca17667583930779d5267fea467ac0c293ebcebc1221ba297a",
    "run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh": "4204d28d8d46c3c4ca57be65f228ad8bfaf472b6cd45483e80bcf12804f9ebd8",
    "supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh": "770d9fc44f2bb7cf3afd4b7ee582e77c76ebca5fd194a574c56cc073eac0a554",
    "run-q38-a59-host-controlled.sh": "a3599e924eb3a3a3cd89df8104747f139c5aa3cf05a380223fce0f34a5d6675c",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")

GRAPH_ENV_RULES = """$0 == "export XPU_GRAPH=0" {
  print "unset XPU_GRAPH VLLM_XPU_GRAPH VLLM_XPU_FORCE_GRAPH_WITH_COMM VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"
  print "export VLLM_XPU_ENABLE_XPU_GRAPH=1"
  next
}
$0 == "export VLLM_XPU_GRAPH=0" { next }
$0 == "export VLLM_XPU_ENABLE_XPU_GRAPH=0" { next }
$0 == "export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0" { next }
$0 == "export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0" { next }
"""

COMPILATION_RULE = """$0 == "    generation_config='\\''vllm'\\'', load_format='\\''safetensors'\\'', async_scheduling=False," {
  print
  print "    compilation_config={"
  print "        '\\''mode'\\'': 0, '\\''cudagraph_mode'\\'': '\\''FULL_DECODE_ONLY'\\'',"
  print "        '\\''cudagraph_capture_sizes'\\'': [1],"
  print "        '\\''max_cudagraph_capture_size'\\'': 1, '\\''compile_sizes'\\'': [],"
  print "        '\\''cudagraph_num_of_warmups'\\'': 1,"
  print "    },"
  print "    cudagraph_metrics=True,"
  next
}
"""

ASSERT_RULE = """$0 == "assert config.cache_config.kv_cache_memory_bytes == kv_cache_memory_bytes" {
  print
  print "assert config.model_config.enforce_eager is False"
  print "assert config.compilation_config.mode.name == '\\''NONE'\\''"
  print "assert config.compilation_config.cudagraph_mode.name == '\\''FULL_DECODE_ONLY'\\''"
  print "assert config.compilation_config.cudagraph_capture_sizes == [1]"
  print "assert config.compilation_config.max_cudagraph_capture_size == 1"
  print "assert config.compilation_config.compile_sizes == []"
  print "assert config.compilation_config.cudagraph_num_of_warmups == 1"
  print "assert config.observability_config.cudagraph_metrics is True"
  next
}
"""

ENFORCE_EAGER_RULE = """$0 == "  --enforce-eager" {
  print "  --compilation-config '\\''{\\"mode\\":0,\\"cudagraph_mode\\":\\"FULL_DECODE_ONLY\\",\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1,\\"compile_sizes\\":[],\\"cudagraph_num_of_warmups\\":1}'\\''"
  print "  --cudagraph-metrics"
  next
}
"""

GRAPH_IDENTITY_PRINTS = """  print "  printf '\\''graph_enable_env=VLLM_XPU_ENABLE_XPU_GRAPH=1\\\\n'\\''"
  print "  printf '\\''compilation_config={\\"mode\\":0,\\"cudagraph_mode\\":\\"FULL_DECODE_ONLY\\",\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1,\\"compile_sizes\\":[],\\"cudagraph_num_of_warmups\\":1}\\\\n'\\''"
"""

OLD_ASSERTIONS = """grep -Fxq 'export VLLM_XPU_ENABLE_XPU_GRAPH=1' "$derived"
! grep -Fq -- '--enforce-eager' "$derived"
grep -Fq '"cudagraph_mode":"FULL_DECODE_ONLY"' "$derived"
grep -Fxq '  --cudagraph-metrics' "$derived"
"""
NEW_ASSERTIONS = """grep -Fxq 'export XPU_GRAPH=0' "$derived"
! grep -Fq 'VLLM_XPU_ENABLE_XPU_GRAPH=1' "$derived"
grep -Fxq '  --enforce-eager' "$derived"
! grep -Fq 'cudagraph_mode' "$derived"
! grep -Fq -- '--cudagraph-metrics' "$derived"
grep -Fq 'moe_backend=triton eager=1 graph=none mtp=%s' "$derived"
! grep -Fq 'graph=FULL_DECODE_ONLY' "$derived"
"""


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    return data.decode()


def successor(text: str) -> str:
    def rename(segment: str) -> str:
        segment = segment.replace("attempt59", "attempt60")
        segment = segment.replace("19731", "19732")
        segment = segment.replace("ATTEMPT=59", "ATTEMPT=60")
        segment = segment.replace("a59", "a60")
        segment = segment.replace("A59", "A60")
        return segment.replace("fullgraph", "nograph")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19731" not in out and "fullgraph" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:90]!r}"
    return text.replace(old, new)


def replace_n(text: str, old: str, new: str, n: int) -> str:
    assert text.count(old) == n, f"anchor count {text.count(old)} != {n}: {old[:90]!r}"
    return text.replace(old, new)


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    # Graph rules out; the eager base lines survive.
    launcher = replace_once(launcher, GRAPH_ENV_RULES, "")
    launcher = replace_once(launcher, COMPILATION_RULE, "")
    launcher = replace_once(launcher, ASSERT_RULE, "")
    launcher = replace_once(launcher, ENFORCE_EAGER_RULE, "")
    launcher = replace_once(launcher, GRAPH_IDENTITY_PRINTS, "")
    launcher = replace_n(
        launcher,
        "diagnostics=full-decode-graph-public-oneccl-torch-trace",
        "diagnostics=nograph-public-oneccl-torch-trace",
        3,
    )
    launcher = replace_once(
        launcher, '  gsub(/enforce_eager=True/, "enforce_eager=False")\n', ""
    )
    launcher = replace_once(
        launcher,
        '  gsub(/moe_backend=triton eager=1/, "moe_backend=triton eager=0 graph=FULL_DECODE_ONLY")\n',
        '  gsub(/moe_backend=triton eager=1/, "moe_backend=triton eager=1 graph=none")\n',
    )
    launcher = replace_once(
        launcher,
        '  gsub(/First-load launcher/, "Full-graph launcher")\n',
        '  gsub(/First-load launcher/, "No-graph control launcher")\n',
    )
    launcher = replace_once(launcher, OLD_ASSERTIONS, NEW_ASSERTIONS)
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A60_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a60-base.sh").unlink(missing_ok=True)
    assert "  --enforce-eager\n" in derived
    assert "cudagraph" not in derived and "VLLM_XPU_ENABLE_XPU_GRAPH=1" not in derived
    assert "export XPU_GRAPH=0\n" in derived
    assert "eager=1 graph=none" in derived
    assert "diagnostics=nograph-public-oneccl-torch-trace" in derived
    assert "q38-ple2k-a60" in derived and "fullgraph" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=8e4ebce78bf5c0ca17667583930779d5267fea467ac0c293ebcebc1221ba297a",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=4204d28d8d46c3c4ca57be65f228ad8bfaf472b6cd45483e80bcf12804f9ebd8",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a59-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=770d9fc44f2bb7cf3afd4b7ee582e77c76ebca5fd194a574c56cc073eac0a554",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a60-nograph-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh", supervisor)
    emit("run-q38-a60-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a60-nograph-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh",
        "run-q38-a60-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
