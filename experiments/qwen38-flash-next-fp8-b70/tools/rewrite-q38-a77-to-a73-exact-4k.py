#!/usr/bin/env python3
"""Create the A73 exact-4K packet from frozen A77 (deterministic graph line at 4352 tokens).

A76 and A77, two independently started servers of the deterministic
full-decode-graph identity served at 4352 tokens, were logit-exact through
4096-token prefill and produced one 4K continuation
(c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639) and the
2304 servers' 2K continuation
(afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714). A73 is
the byte-identical server at attempt 73 / port 19745 on which the frozen
client battery runs (recovery canary, quality suite with 16-repeat and exact
2K needle, three short rows, two exact-2K rows) extended by two exact-4K rows
(`--depth 4096 --context-capacity 4352`, usage 4096/128/4224, cache zero),
with both depth hashes pinned to the deterministic line's own two-server
values. The native-line records (5fd297f7 at 2K, 1d833e5f at 4K) are not
touched; the summary records this as additive.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A73_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh": "5f6a12a2e7405993c931568724a1b50a6647deb40b8b94d0be3a4ccd410942af",
    "run-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32-client.sh": "24616b382d4069e6e3854eee196a4456fb00de090a8b15fe4cf7a560c00b7817",
    "supervise-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh": "0571c73a677fc374fff7e32c030c6f03b2d51904e3f015cc5018bdae55290681",
    "run-q38-a77-host-controlled.sh": "b4ddb347d96ca9c31a6ea0205573b0ca497163f6ece409395a832368efbaf5bc",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
EXACT_2K = "afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714"
EXACT_4K = "c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639"
PROMPT_4K = "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0"
PAYLOAD_4K = "2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be"


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
        segment = segment.replace("attempt77", "attempt73")
        segment = segment.replace("19749", "19745")
        segment = segment.replace("ATTEMPT=77", "ATTEMPT=73")
        segment = segment.replace("a77", "a73")
        return segment.replace("A77", "A73")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19749" not in out and "attempt77" not in out
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


def extend_client(client: str) -> str:
    # 1. Pre-existence guard covers the 4K artifacts too.
    client = replace_once(
        client,
        "  exact-depth-2k-r1.json exact-depth-2k-r2.json ple-only-qsa-stable-summary.json \\\n",
        "  exact-depth-2k-r1.json exact-depth-2k-r2.json exact-depth-4k-r1.json exact-depth-4k-r2.json \\\n"
        "  ple-only-qsa-stable-summary.json \\\n",
    )
    client = replace_once(
        client,
        "  exact-depth-2k-r2.log exact-depth-2k-r2.rc; do\n",
        "  exact-depth-2k-r2.log exact-depth-2k-r2.rc exact-depth-4k-r1.log exact-depth-4k-r1.rc \\\n"
        "  exact-depth-4k-r2.log exact-depth-4k-r2.rc; do\n",
    )
    # 2. The served KV cache must cover a 4,224-token request, not only 2,176.
    client = replace_once(
        client,
        'assert int(labels.get("kv_cache_size_tokens", "0")) >= 2176, labels\n',
        'assert int(labels.get("kv_cache_size_tokens", "0")) >= 4224, labels\n',
    )
    # 3. The exact-2K rows state the real served capacity (the request payload
    #    and its hash do not include this argument); then two exact-4K rows.
    client = replace_once(
        client,
        "    --fixture \"$fixture\" --depth 2048 --context-capacity 2304 \\\n",
        "    --fixture \"$fixture\" --depth 2048 --context-capacity 4352 \\\n",
    )
    two_k_loop_end = (
        "  write_atomic \"${run_dir}/exact-depth-2k-r${row}.rc\" \"$rc\"\n"
        "  (( rc == 0 )) || exit \"$rc\"\n"
        "done\n"
    )
    four_k_loop = two_k_loop_end + (
        "\n"
        "for row in 1 2; do\n"
        "  set +e\n"
        "  timeout --signal=TERM --kill-after=10s 1500s \"$python\" \"$depth_harness\" --execute \\\n"
        "    --fixture \"$fixture\" --depth 4096 --context-capacity 4352 \\\n"
        "    --base-url \"$base_url\" --model \"$model\" --response-adapter vllm --timeout 1400 \\\n"
        "    --out \"${run_dir}/exact-depth-4k-r${row}.json\" \\\n"
        "    >\"${run_dir}/exact-depth-4k-r${row}.log\" 2>&1\n"
        "  rc=$?\n"
        "  set -e\n"
        "  write_atomic \"${run_dir}/exact-depth-4k-r${row}.rc\" \"$rc\"\n"
        "  (( rc == 0 )) || exit \"$rc\"\n"
        "done\n"
    )
    client = replace_once(client, two_k_loop_end, four_k_loop)
    # 4. Summary: the 2K pin stays; the 4K rows are checked the same way.
    two_k_pin = f"assert depth_hashes == ['{EXACT_2K}'] * 2\n"
    four_k_block = two_k_pin + (
        "depth4k = [json.loads((root / f\"exact-depth-4k-r{i}.json\").read_text()) for i in range(1, 3)]\n"
        "for item in depth4k:\n"
        "    assert item[\"status\"] == \"passed\" and item[\"gate\"][\"passed\"] is True\n"
        f"    assert item[\"request\"][\"prompt_token_ids_sha256\"] == \"{PROMPT_4K}\"\n"
        f"    assert item[\"request\"][\"request_payload_sha256\"] == \"{PAYLOAD_4K}\"\n"
        "    usage = item[\"response\"][\"usage\"]\n"
        "    assert (usage[\"prompt_tokens\"], usage[\"completion_tokens\"], usage[\"total_tokens\"]) == (4096, 128, 4224)\n"
        "    assert usage[\"prompt_tokens_details\"][\"cached_tokens\"] == 0\n"
        "    assert item[\"response\"][\"finish_reasons\"] == [\"length\"] and len(item[\"response\"][\"token_ids\"]) == 128\n"
        "depth4k_hashes = [item[\"response\"][\"output_token_ids_sha256\"] for item in depth4k]\n"
        "assert len(set(depth4k_hashes)) == 1\n"
        f"assert depth4k_hashes == ['{EXACT_4K}'] * 2\n"
    )
    client = replace_once(client, two_k_pin, four_k_block)
    exact_2k_tail = (
        "        \"same_boot_output_repeat\": True,\n"
        "        \"cached_tokens\": [0, 0],\n"
        "    },\n"
        "    \"protected_results_changed\": False,\n"
    )
    exact_4k_section = (
        "        \"same_boot_output_repeat\": True,\n"
        "        \"cached_tokens\": [0, 0],\n"
        "    },\n"
        "    \"exact_4k\": {\n"
        "        \"repeats\": 2,\n"
        "        \"protocol\": \"p4096/o128; conventional 99 inter-token intervals; served capacity 4352\",\n"
        "        \"rates_tok_s_conventional_99_interval\": [d[\"metric_window\"][\"conventional_99_interval_tok_s\"] for d in depth4k],\n"
        "        \"median_tok_s_conventional_99_interval\": statistics.median(d[\"metric_window\"][\"conventional_99_interval_tok_s\"] for d in depth4k),\n"
        "        \"ttft_s\": [d[\"metric_window\"][\"time_to_first_token_s\"] for d in depth4k],\n"
        "        \"output_token_ids_sha256\": depth4k_hashes[0],\n"
        "        \"same_boot_output_repeat\": True,\n"
        "        \"cached_tokens\": [0, 0],\n"
        "    },\n"
        "    \"protected_results_changed\": False,\n"
    )
    client = replace_once(client, exact_2k_tail, exact_4k_section)
    client = replace_once(
        client,
        "             \"exact-depth-2k-r1.json\", \"exact-depth-2k-r2.json\"]:\n",
        "             \"exact-depth-2k-r1.json\", \"exact-depth-2k-r2.json\",\n"
        "             \"exact-depth-4k-r1.json\", \"exact-depth-4k-r2.json\"]:\n",
    )
    client = replace_once(
        client,
        "    \"interpretation\": \"Additive PLE-only TP4 compilation-free FULL_DECODE_ONLY quality, short, and exact-2K screen; it does not replace or lower any prior row.\",\n",
        "    \"interpretation\": \"Additive PLE-only TP4 compilation-free FULL_DECODE_ONLY deterministic-line quality, short, exact-2K and exact-4K screen at 4352 served tokens; both depth hashes are the deterministic line's own two-server authorities; it does not replace or lower any prior row or native-line record.\",\n",
    )
    client = replace_once(
        client,
        "'PASS recovery quality short-repeat exact-2K-repeat PLE-only 2K MTP0 QSA-stable treatment'",
        "'PASS recovery quality short-repeat exact-2K-repeat exact-4K-repeat PLE-only 4352 MTP0 QSA-stable treatment'",
    )
    return client


def main() -> None:
    launcher = source("launch-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A73_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a73-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a73" in derived and "q38-ple2k-a77" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert 'expected_vllm_head="2169dbfe38c2954edc5ae50e94f68d45be071b79"' in derived
    assert '[[ "${max_model_len}" == "4352" ]] || {' in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = extend_client(
        successor(source("run-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32-client.sh"))
    )
    assert client.count("--context-capacity 4352") == 2 and "--context-capacity 2304" not in client
    assert client.count(EXACT_4K) == 1 and client.count(EXACT_2K) == 1
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=5f6a12a2e7405993c931568724a1b50a6647deb40b8b94d0be3a4ccd410942af",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=24616b382d4069e6e3854eee196a4456fb00de090a8b15fe4cf7a560c00b7817",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a77-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=0571c73a677fc374fff7e32c030c6f03b2d51904e3f015cc5018bdae55290681",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a73-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh",
        "run-q38-a73-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
