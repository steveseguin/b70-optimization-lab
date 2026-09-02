#!/usr/bin/env python3
"""Create A56 from frozen A55 with the tuned M1 W13-N32 map as the sole change.

A55 ran the full-graph TP4/EP4 MTP0 PLE-only endpoint without any tuned MoE
folder, so its M1 Triton MoE used vLLM's default entry (N64 for both GEMMs,
four warps). A56 keeps every A55 identity (external checkpoint, twoshots,
host guards, battery, protected hashes) and exports
`VLLM_TUNED_CONFIG_FOLDER=configs/moe-m1-w13-n32`, the map that carries the
component-qualified M1 entry: eight warps plus a nested `W1_CONFIG`
`BLOCK_SIZE_N=32` delta for the W13 launch only. The launcher receipts the
folder and map hash, the client proves the live server environment carries
exactly that folder and re-runs the official resolver verifier into the run
directory, and the supervisor requires the new identity keys before a valid
stop.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A56_REWRITE_VALIDATE_ONLY") == "1"
FOLDER = "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"
BASE_FOLDER = "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1"
CONFIG_NAME = (
    "E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,"
    "dtype=fp8_w8a8,block_shape=[128,128].json"
)
MAP_SHA = "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be"
BASE_MAP_SHA = "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464"
PHASE_PATCH = (
    "/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm/"
    "0021-Add-opt-in-per-phase-Triton-MoE-configs.patch"
)
PHASE_PATCH_SHA = "ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519"
VERIFIER_SHA = "a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f"
FOLDER_LABEL = "moe-m1-w13-n32"

SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh": "acc6c5590f5c49fc979405235b62a2ef3540a63e6c4d960bbef31d1c05422c66",
    "run-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots-client.sh": "d3289f938ee6d0ec59581b5c660a4c7f1503c780dac85a96ca8d24245acaa5ed",
    "supervise-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh": "ada6baf29edec39fd91b2b69c8819083cb529f915fa99900509db1aa200b0020",
    "run-q38-a55-host-controlled.sh": "e70543b364a3f76ca74a9f04a32bf67fd7031b30de05c020ebf1c001c6a6006e",
}


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    return data.decode()


# 64-hex file digests and 40-hex Git heads are identity tokens; never rename
# inside them.
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")


def successor(text: str) -> str:
    """Rename attempt markers everywhere except inside 64-hex hash tokens.

    The frozen oneCCL kernel hash `0d549c35a558f1b2...` contains the substring
    `a55`, so a blind replacement would corrupt a frozen identity; hashes are
    passed through untouched.
    """

    def rename(segment: str) -> str:
        segment = segment.replace("attempt55", "attempt56")
        segment = segment.replace("19727", "19728")
        segment = segment.replace("ATTEMPT=55", "ATTEMPT=56")
        segment = segment.replace("a55", "a56")
        segment = segment.replace("A55", "A56")
        # The A56 files carry the treatment in their names; twoshots stays in
        # the identity receipts because it is unchanged from A55.
        return segment.replace(
            "ple-only-a56-fullgraph-twoshots", "ple-only-a56-fullgraph-w13n32"
        )

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "a55" not in HASH_TOKEN.sub("", out) and "19727" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:80]!r}"
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
    map_path = Path(FOLDER) / CONFIG_NAME
    assert digest(map_path.read_bytes()) == MAP_SHA, "candidate map drifted"
    assert digest((Path(BASE_FOLDER) / CONFIG_NAME).read_bytes()) == BASE_MAP_SHA
    assert digest(Path(PHASE_PATCH).read_bytes()) == PHASE_PATCH_SHA
    assert (
        digest((ROOT / "verify-moe-m1-w13-n32-selection.py").read_bytes())
        == VERIFIER_SHA
    )

    # ---- launcher ---------------------------------------------------------
    launcher = source("launch-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh")
    old_derived = "expected_derived=85eeb5312e884813862dea86a895ce4c5838605f931b26b6452b6b0d130feb3a"
    launcher = replace_once(launcher, old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    # Static map identity immediately after the campaign name.
    launcher = replace_once(
        launcher,
        "campaign=qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1\n",
        "campaign=qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1\n"
        f"tuned_config_folder={FOLDER}\n"
        f"tuned_config_map='{FOLDER}/{CONFIG_NAME}'\n"
        f'[[ "$(sha256sum "$tuned_config_map" | cut -d\' \' -f1)" == {MAP_SHA} ]] || '
        "{ printf 'FAIL: A56 tuned M1 map drifted\\n' >&2; exit 1; }\n"
        '[[ "$(jq -r \'."1".num_warps\' "$tuned_config_map")" == 8 && '
        '"$(jq -r \'."1".W1_CONFIG.BLOCK_SIZE_N\' "$tuned_config_map")" == 32 && '
        '"$(jq -r \'."1" | has("W2_CONFIG")\' "$tuned_config_map")" == false ]] || '
        "{ printf 'FAIL: A56 tuned M1 map entry is not the qualified W13-N32 shape\\n' >&2; exit 1; }\n",
    )
    # Export the folder next to the other frozen server environment exports.
    launcher = replace_once(
        launcher,
        '  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"\n',
        '  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"\n'
        f'  print "export VLLM_TUNED_CONFIG_FOLDER={FOLDER}"\n',
    )
    # Identity receipts.
    launcher = replace_once(
        launcher,
        """  print "  printf '\\''ccl_sycl_allreduce_ll=twoshots\\\\n'\\''"\n""",
        """  print "  printf '\\''ccl_sycl_allreduce_ll=twoshots\\\\n'\\''"\n"""
        f"""  print "  printf '\\''tuned_config_folder={FOLDER_LABEL}\\\\n'\\''"\n"""
        f"""  print "  printf '\\''tuned_config_map_sha256={MAP_SHA}\\\\n'\\''"\n""",
    )
    # Derived-source assertions.
    launcher = replace_once(
        launcher,
        """[[ "$(grep -Fxc "  printf 'ccl_sycl_allreduce_ll=twoshots\\\\n'" "$derived")" == 1 ]]\n""",
        """[[ "$(grep -Fxc "  printf 'ccl_sycl_allreduce_ll=twoshots\\\\n'" "$derived")" == 1 ]]\n"""
        f"""[[ "$(grep -Fxc 'export VLLM_TUNED_CONFIG_FOLDER={FOLDER}' "$derived")" == 1 ]]\n"""
        f"""[[ "$(grep -Fxc "  printf 'tuned_config_folder={FOLDER_LABEL}\\\\n'" "$derived")" == 1 ]]\n"""
        f"""[[ "$(grep -Fxc "  printf 'tuned_config_map_sha256={MAP_SHA}\\\\n'" "$derived")" == 1 ]]\n""",
    )
    env = os.environ.copy()
    env["Q38_A56_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a56-base.sh").unlink(missing_ok=True)
    assert f"export VLLM_TUNED_CONFIG_FOLDER={FOLDER}\n" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    # ---- client -----------------------------------------------------------
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots-client.sh")
    )
    client = replace_once(
        client,
        "if grep -zFq 'VLLM_TUNED_CONFIG_FOLDER=' \"/proc/${server_pid}/environ\"; then\n"
        "  printf 'FAIL: tuned MoE folder unexpectedly present in server environment\\n' >&2\n"
        "  exit 1\n"
        "fi\n",
        f"grep -zFxq 'VLLM_TUNED_CONFIG_FOLDER={FOLDER}' \"/proc/${{server_pid}}/environ\" || {{\n"
        "  printf 'FAIL: live server lacks the exact A56 tuned M1 map folder\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        f"[[ \"$(grep -zc 'VLLM_TUNED_CONFIG_FOLDER=' \"/proc/${{server_pid}}/environ\" | tr -d '\\n')\" == 1 ]] || {{\n"
        "  printf 'FAIL: more than one tuned folder selector in server environment\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        f"[[ \"$(sha256sum '{FOLDER}/{CONFIG_NAME}' | cut -d' ' -f1)\" == {MAP_SHA} ]] || {{\n"
        "  printf 'FAIL: A56 tuned M1 map drifted before client work\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        f'[[ "$(sha256sum "${{repo}}/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py" | cut -d\' \' -f1)" == {VERIFIER_SHA} ]] || {{\n'
        "  printf 'FAIL: W13-N32 selection verifier drifted\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        "# The official resolver needs the server's XPU runtime identity to resolve\n"
        "# the platform and device name; mirror the frozen server exports exactly.\n"
        "env PYTHONPATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70:/home/steve/src/vllm-current-main \\\n"
        "  LD_LIBRARY_PATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib \\\n"
        "  ZE_AFFINITY_MASK=0 VLLM_TARGET_DEVICE=xpu \\\n"
        f"  VLLM_TUNED_CONFIG_FOLDER={FOLDER} \\\n"
        f'  "$python" "${{repo}}/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py" \\\n'
        f"  --base-config-file '{BASE_FOLDER}/{CONFIG_NAME}' \\\n"
        f"  --candidate-config-file '{FOLDER}/{CONFIG_NAME}' \\\n"
        "  --vllm-source /home/steve/src/vllm-current-main \\\n"
        f"  --phase-config-patch {PHASE_PATCH} \\\n"
        '  --output "${run_dir}/moe-m1-w13-n32-selection-receipt.json" || {\n'
        "  printf 'FAIL: official W13-N32 resolver receipt failed\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        'jq -e \'.status == "pass" and .selected_batch_key == 1 and\n'
        "  .m1.w13.BLOCK_SIZE_N == 32 and .m1.w13.num_warps == 8 and\n"
        "  .m1.w2.BLOCK_SIZE_N == 64 and .m1.w2.num_warps == 8 and\n"
        f'  .config.candidate_sha256 == "{MAP_SHA}" and\n'
        "  .preservation.all_integer_m_2_through_512_match_retained_map == true' \\\n"
        '  "${run_dir}/moe-m1-w13-n32-selection-receipt.json" >/dev/null || {\n'
        "  printf 'FAIL: W13-N32 resolver receipt did not prove key 1 W13-N32 / W2-N64\\n' >&2\n"
        "  exit 1\n"
        "}\n",
    )
    client = replace_once(
        client,
        "  'ccl_sycl_allreduce_ll=twoshots'; do\n",
        "  'ccl_sycl_allreduce_ll=twoshots' \\\n"
        f"  'tuned_config_folder={FOLDER_LABEL}' 'tuned_config_map_sha256={MAP_SHA}'; do\n",
    )
    client = replace_once(
        client,
        '        "ccl_sycl_allreduce_ll": "twoshots",\n',
        '        "ccl_sycl_allreduce_ll": "twoshots",\n'
        f'        "tuned_config_folder": "{FOLDER_LABEL}",\n'
        f'        "tuned_config_map_sha256": "{MAP_SHA}",\n',
    )

    # ---- supervisor -------------------------------------------------------
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh")
    )
    supervisor = replace_once(
        supervisor,
        '         .identity.ccl_sycl_allreduce_ll == "twoshots" and\n',
        '         .identity.ccl_sycl_allreduce_ll == "twoshots" and\n'
        f'         .identity.tuned_config_folder == "{FOLDER_LABEL}" and\n'
        f'         .identity.tuned_config_map_sha256 == "{MAP_SHA}" and\n',
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=acc6c5590f5c49fc979405235b62a2ef3540a63e6c4d960bbef31d1c05422c66",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=d3289f938ee6d0ec59581b5c660a4c7f1503c780dac85a96ca8d24245acaa5ed",
        "expected_client=" + digest(client),
    )

    # ---- host wrapper -----------------------------------------------------
    host = successor(source("run-q38-a55-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=ada6baf29edec39fd91b2b69c8819083cb529f915fa99900509db1aa200b0020",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh", supervisor)
    emit("run-q38-a56-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh",
        "run-q38-a56-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
