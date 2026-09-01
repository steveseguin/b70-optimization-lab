#!/usr/bin/env python3
"""Mechanically derive the A33 full-graph endpoint from the frozen A28 lane."""

from __future__ import annotations

import argparse
import re
import sys


CURRENT_VLLM = "797769b34b6db5c934609b75dc04cc61ec66e5f9"
CURRENT_KERNEL_SOURCE = "e421889999bc1e5a5f11044d14548b9afdba644d"
COMPILATION_JSON = (
    '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY",'
    '"cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,'
    '"compile_sizes":[],"cudagraph_num_of_warmups":1}'
)
LIBCCL = "/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"
LIBCCL_SHA256 = "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
CCL_KERNEL_PATH = "/home/steve/.venvs/vllm-xpu/lib/ccl/kernels"
CCL_KERNEL_SHA256 = "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9"


class RewriteError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RewriteError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RewriteError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def common_identity(text: str) -> str:
    text = text.replace("ple-only-a28-profile", "ple-only-a33-fullgraph")
    text = text.replace("q38-mtp0-ple-only-a28", "q38-mtp0-ple-only-a33")
    text = text.replace("q38-ple-only-a28", "q38-ple-only-a33")
    text = text.replace("q38-ple4k-a28", "q38-ple4k-a33")
    text = text.replace("attempt28", "attempt33")
    text = text.replace("19700", "19705")
    text = text.replace("A28", "A33")
    text = text.replace("target-step-xpu-profile", "full-decode-graph-public-oneccl")
    text = text.replace("ep4-eager-mtp", "ep4-fullgraph-mtp")
    text = text.replace("triton_eager_mtp", "triton_fullgraph_mtp")
    text = text.replace("First-load launcher", "Full-graph launcher")
    text = text.replace("d14396e27247c1b251da0ce24a0942772c4b002f", CURRENT_VLLM)
    return text


def launcher(text: str, derived_hash: str) -> str:
    text = common_identity(text)
    text = replace_once(
        text,
        'base="${script_dir}/launch-tp4-ep4-fullgraph-mtp0-long-context-base.sh"',
        'base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"',
        "historical source filename",
    )
    text = replace_once(
        text,
        '$0 == "campaign=\\"qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp${mtp}${exact_suffix}-${max_model_len}-r1\\"" {',
        '$0 == "campaign=\\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-r1\\"" {',
        "historical campaign match predicate",
    )
    text = replace_once(
        text,
        "$0 == \"print(f'\\''engine_config=tp4_ep4_triton_fullgraph_mtp{mtp}_selective_ple_and_embed_uva'\\'')\" {",
        "$0 == \"print(f'\\''engine_config=tp4_ep4_triton_eager_mtp{mtp}_selective_ple_and_embed_uva'\\'')\" {",
        "historical engine-config match predicate",
    )
    text = replace_once(
        text,
        "expected_derived=4a738f678c06707644e3ac5b89d76631e5ba8d61d0a9637887663ef400445905",
        f"expected_derived={derived_hash}",
        "derived hash",
    )
    text = (
        replace_once(
            text,
            '  print "expected_vllm_head=\\"d14396e27247c1b251da0ce24a0942772c4b002f\\""',
            f'  print "expected_vllm_head=\\"{CURRENT_VLLM}\\""',
            "nested vLLM head",
        )
        if "d14396e27247c1b251da0ce24a0942772c4b002f" in text
        else text
    )

    graph_rules_anchor = """$0 == "unset VLLM_PLE_CPU_OFFLOAD" {
  print
  print "unset VLLM_XPU_PLE_UVA_PREFETCH"
  next
}
"""
    kernel_source_rule = f'''$0 == "  expected_kernels_head=\\"ad25aa9f69a2171612b9c6b83dfa82c69559f9e4\\"" {{
  print "  expected_kernels_head=\\"{CURRENT_KERNEL_SOURCE}\\""
  next
}}
'''
    graph_rules = (
        graph_rules_anchor
        + kernel_source_rule
        + """$0 == "export XPU_GRAPH=0" {
  print "unset XPU_GRAPH VLLM_XPU_GRAPH VLLM_XPU_FORCE_GRAPH_WITH_COMM VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"
  print "export VLLM_XPU_ENABLE_XPU_GRAPH=1"
  next
}
$0 == "export VLLM_XPU_GRAPH=0" { next }
$0 == "export VLLM_XPU_ENABLE_XPU_GRAPH=0" { next }
$0 == "export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0" { next }
$0 == "export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0" { next }
$0 == "export CCL_TOPO_P2P_ACCESS=1" {
  print
  print "export CCL_KERNEL_PATH=/home/steve/.venvs/vllm-xpu/lib/ccl/kernels"
  print "export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096"
  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"
  next
}
$0 == "    generation_config='\\''vllm'\\'', load_format='\\''safetensors'\\'', async_scheduling=False," {
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
$0 == "assert config.cache_config.kv_cache_memory_bytes == kv_cache_memory_bytes" {
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
$0 == "  --enforce-eager" {
  print "  --compilation-config '\\''{\\"mode\\":0,\\"cudagraph_mode\\":\\"FULL_DECODE_ONLY\\",\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1,\\"compile_sizes\\":[],\\"cudagraph_num_of_warmups\\":1}'\\''"
  print "  --cudagraph-metrics"
  next
}
index($0, "diagnostics=none") > 0 {
  gsub(/diagnostics=none/, "diagnostics=full-decode-graph-public-oneccl")
  print
  print "  printf '\\''graph_enable_env=VLLM_XPU_ENABLE_XPU_GRAPH=1\\\\n'\\''"
  print "  printf '\\''compilation_config={\\"mode\\":0,\\"cudagraph_mode\\":\\"FULL_DECODE_ONLY\\",\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1,\\"compile_sizes\\":[],\\"cudagraph_num_of_warmups\\":1}\\\\n'\\''"
  print "  printf '\\''libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700\\\\n'\\''"
  print "  printf '\\''ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9\\\\n'\\''"
  next
}
index($0, "if ! timeout 180s ") == 1 && index($0, "torch.distributed.run") > 0 {
  print "echo 43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700  /mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0 | sha256sum -c -"
  print "echo 0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9  /home/steve/.venvs/vllm-xpu/lib/ccl/kernels/kernels.spv | sha256sum -c -"
  print ""
  print
  next
}
"""
    )
    text = replace_once(text, graph_rules_anchor, graph_rules, "graph rule injection")
    text = replace_once(
        text,
        '  print "[[ -z \\"$(git -C \\"${vllm_src}\\" status --porcelain)\\" ]] || fail \\"vLLM overlay became dirty immediately before launch\\""\n  print\n',
        '  print "[[ -z \\"$(git -C \\"${vllm_src}\\" status --porcelain)\\" ]] || fail \\"vLLM overlay became dirty immediately before launch\\""\n'
        f'  print "echo {LIBCCL_SHA256}  {LIBCCL} | sha256sum -c -"\n'
        f'  print "echo {CCL_KERNEL_SHA256}  {CCL_KERNEL_PATH}/kernels.spv | sha256sum -c -"\n'
        "  print\n",
        "pre-serve hash gates",
    )
    text = replace_once(
        text,
        '  gsub(/12\\.25/, "12.0")\n',
        '  gsub(/enforce_eager=True/, "enforce_eager=False")\n'
        '  gsub(/moe_backend=triton eager=1/, "moe_backend=triton eager=0 graph=FULL_DECODE_ONLY")\n'
        '  gsub(/qwen38-flash-next-fp8-tp4-ep4-eager-mtp/, "qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp")\n'
        '  gsub(/tp4_ep4_triton_eager_mtp/, "tp4_ep4_triton_fullgraph_mtp")\n'
        '  gsub(/First-load launcher/, "Full-graph launcher")\n'
        '  gsub(/12\\.25/, "12.0")\n',
        "graph substitutions",
    )

    boot_pattern = re.compile(
        r'\nif \[\[ "\$\{Q38_A33_VALIDATE_ONLY:-0\}" != 1 \]\]; then\n'
        r".*?\nfi\n\n(?=export MODEL_PATH=)",
        re.DOTALL,
    )
    resource_gates = """
if [[ "${Q38_A33_VALIDATE_ONLY:-0}" != 1 ]]; then
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
  nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
  (( mem_available_kib >= 120000000 )) || { printf 'FAIL: A33 requires MemAvailable >= 120000000 KiB\\n' >&2; exit 1; }
  (( swap_free_kib >= 8000000 )) || { printf 'FAIL: A33 requires SwapFree >= 8000000 KiB\\n' >&2; exit 1; }
  (( nvme_available_bytes >= 220000000000 )) || { printf 'FAIL: A33 requires >= 220000000000 free NVMe bytes\\n' >&2; exit 1; }
fi

"""
    text, count = boot_pattern.subn(lambda _match: resource_gates, text, count=1)
    if count != 1:
        raise RewriteError(
            f"one-load boot rule removal: expected one block, found {count}"
        )
    text = replace_once(
        text,
        "export VLLM_BIN=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/vllm-serve-with-q38-a28-profiler.py\nexport Q38_A33_PROFILE_DIR=/mnt/fast-ai/q38-profiles/attempt33",
        "export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm",
        "profiler removal",
    )
    text = replace_once(
        text,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=28 PORT=19705",
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=33 PORT=19705",
        "attempt identity",
    )
    text = replace_once(
        text,
        '[[ "$(sha256sum "$derived" | cut -d\' \' -f1)" == "$expected_derived" ]]',
        'if [[ "${Q38_A33_DERIVED_SOURCE_ONLY:-0}" == 1 ]]; then cat "$derived"; exit 0; fi\n'
        '[[ "$(sha256sum "$derived" | cut -d\' \' -f1)" == "$expected_derived" ]]',
        "derived source escape hatch",
    )

    static_anchor = "! grep -Fq 'exact_12.22' \"$derived\"\n"
    static_checks = (
        static_anchor
        + f"""grep -Fxq 'export VLLM_XPU_ENABLE_XPU_GRAPH=1' "$derived"
! grep -Fq -- '--enforce-eager' "$derived"
grep -Fq '\"cudagraph_mode\":\"FULL_DECODE_ONLY\"' "$derived"
grep -Fxq '  --cudagraph-metrics' "$derived"
grep -Fxq 'export LD_PRELOAD={LIBCCL}' "$derived"
grep -Fxq 'export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096' "$derived"
grep -Fxq 'export CCL_KERNEL_PATH={CCL_KERNEL_PATH}' "$derived"
! grep -Fq 'q38-flash-next-full-load.boot-id' "$derived"
! grep -Fq 'ep4-eager' "$derived"
! grep -Fq 'triton_eager' "$derived"
"""
    )
    text = replace_once(text, static_anchor, static_checks, "static graph checks")
    return text


def client(text: str, runtime_verifier_hash: str) -> str:
    text = common_identity(text)
    text = replace_count(
        text,
        "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
        CURRENT_KERNEL_SOURCE,
        2,
        "client kernel source identity",
    )
    text = replace_once(
        text,
        "completed=0\n",
        "runtime_verifier=${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-q38-a33-fullgraph-runtime.py\n"
        f"expected_runtime_verifier={runtime_verifier_hash}\n"
        "torchinductor_cache=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt33-compile/torchinductor\n"
        f"compilation_json='{COMPILATION_JSON}'\n"
        "completed=0\n",
        "runtime verifier identity",
    )
    text = replace_once(
        text,
        '[[ "$(sha256sum "$fixture" | cut -d\' \' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]] || exit 1\n',
        '[[ "$(sha256sum "$fixture" | cut -d\' \' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]] || exit 1\n'
        '[[ "$(sha256sum "$runtime_verifier" | cut -d\' \' -f1)" == "$expected_runtime_verifier" ]] || exit 1\n',
        "runtime verifier hash gate",
    )
    text = replace_once(
        text,
        "  health-before-client.json models-before-client.json metrics-before-client.prom \\\n",
        "  health-before-client.json models-before-client.json metrics-before-client.prom \\\n"
        "  fullgraph-runtime-before.json fullgraph-runtime-after.json \\\n",
        "runtime evidence no-clobber list",
    )
    profiler_block = re.compile(
        r'\n\[\[ "\$server_command" == \*"--profiler-config"\*.*?\n\}\n\n',
        re.DOTALL,
    )
    text, count = profiler_block.subn("\n", text, count=1)
    if count != 1:
        raise RewriteError(
            f"profiler command removal: expected one block, found {count}"
        )
    text = replace_once(
        text,
        "\n[[ \"$(sha256sum /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-a28-profile-window.sh | cut -d' ' -f1)\" == 17e5bd6957ce4e94931d06b43fdac3ca5c7906ee410d3080382eda4a5bb025ba ]] || exit 1\n"
        "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-a28-profile-window.sh\n",
        "\n",
        "profile execution removal",
    )

    command_anchor = """[[ "$server_command" != *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {
  printf 'FAIL: MTP or reasoning parser unexpectedly present\\n' >&2
  exit 1
}
"""
    command_checks = (
        command_anchor
        + """[[ "$server_command" != *"--enforce-eager"* && "$server_command" == *"--cudagraph-metrics"* && \\
   "$server_command" == *"--compilation-config ${compilation_json}"* ]] || {
  printf 'FAIL: frozen A33 graph command identity mismatch\\n' >&2
  exit 1
}
"""
    )
    text = replace_once(text, command_anchor, command_checks, "graph command checks")

    receipt_anchor = "  'moe_backend=triton eager=1 mtp=0 max_model_len=4352 max_num_batched_tokens=64' \\\n"
    text = replace_once(
        text,
        receipt_anchor,
        "  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=0 max_model_len=4352 max_num_batched_tokens=64' \\\n",
        "graph identity receipt",
    )
    text = replace_once(
        text,
        "  'reasoning_parser=absent' 'diagnostics=full-decode-graph-public-oneccl'; do\n",
        "  'reasoning_parser=absent' 'diagnostics=full-decode-graph-public-oneccl' \\\n"
        "  'graph_enable_env=VLLM_XPU_ENABLE_XPU_GRAPH=1' \\\n"
        f"  'compilation_config={COMPILATION_JSON}' \\\n"
        f"  'libccl_sha256={LIBCCL_SHA256}' 'ccl_kernel_sha256={CCL_KERNEL_SHA256}'; do\n",
        "full graph receipts",
    )
    health_anchor = 'curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" >"${run_dir}/metrics-before-client.prom"\n'
    health_checks = (
        health_anchor
        + """"$python" "$runtime_verifier" \\
  --server-pid "$server_pid" --server-log "${run_dir}/server.log" \\
  --torchinductor-cache "$torchinductor_cache" --phase before \\
  --output "${run_dir}/fullgraph-runtime-before.json"
"""
    )
    text = replace_once(
        text, health_anchor, health_checks, "pre-client runtime verification"
    )

    text = replace_once(
        text,
        '        "tp": 4, "ep": 4, "mtp": 0, "graph": "off", "max_model_len": 4352,\n',
        '        "tp": 4, "ep": 4, "mtp": 0, "graph": "FULL_DECODE_ONLY",\n'
        '        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1],\n'
        '        "max_model_len": 4352,\n',
        "summary graph identity",
    )
    text = replace_once(
        text,
        '        "profiler": "torch_xpu_report_only",\n        "profile_delay_iterations": 65,\n        "profile_max_iterations": 4,\n',
        f'        "libccl_sha256": "{LIBCCL_SHA256}",\n'
        f'        "ccl_kernel_sha256": "{CCL_KERNEL_SHA256}",\n',
        "summary profiler removal",
    )
    text = replace_once(
        text,
        '    "interpretation": "Additive PLE-only TP4 eager MTP0 quality, short, and exact-4K screen; it does not replace or lower any prior row.",\n',
        '    "interpretation": "Additive PLE-only TP4 compilation-free FULL_DECODE_ONLY quality, short, and exact-4K screen; it does not replace or lower any prior row.",\n',
        "summary interpretation",
    )
    final_anchor = "write_atomic \"${run_dir}/client-gates-passed.txt\" 'PASS recovery quality short-repeat exact-4K-repeat PLE-only 4K MTP0 QSA-stable treatment'\n"
    final_checks = (
        f'''"$python" "$runtime_verifier" \\
  --server-pid "$server_pid" --server-log "${{run_dir}}/server.log" \\
  --torchinductor-cache "$torchinductor_cache" --phase after \\
  --output "${{run_dir}}/fullgraph-runtime-after.json"
jq -e '.status == "passed" and .phase == "after" and
  .size_1_full_dispatch_count > 0 and (.collective_processes | length) >= 4 and
  .libccl.sha256 == "{LIBCCL_SHA256}" and
  .ccl_kernel.sha256 == "{CCL_KERNEL_SHA256}" and
  .torchinductor_files == []' "${{run_dir}}/fullgraph-runtime-after.json" >/dev/null

'''
        + final_anchor
    )
    text = replace_once(text, final_anchor, final_checks, "post-client graph use gate")
    return text


def supervisor(text: str, wrapper_hash: str, client_hash: str) -> str:
    text = common_identity(text)
    text = replace_once(
        text,
        "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
        CURRENT_KERNEL_SOURCE,
        "supervisor kernel source identity",
    )
    text = replace_once(
        text,
        "expected_wrapper=492ac0b7cfb0d6f4c64fc2bd1e5ab1ec45222d2dd8ce118f50daeb0dce48f934",
        f"expected_wrapper={wrapper_hash}",
        "wrapper hash",
    )
    text = replace_once(
        text,
        "expected_client=1733790e88afca40409fdfab08d629da6b9e5de4e849dabb897b0fd77625d7cb",
        f"expected_client={client_hash}",
        "client hash",
    )
    text = replace_once(
        text,
        '.identity.graph == "off" and .identity.max_model_len == 4352 and\n',
        '.identity.graph == "FULL_DECODE_ONLY" and\n'
        '.identity.compilation_mode == "NONE" and\n'
        ".identity.cudagraph_capture_sizes == [1] and\n"
        ".identity.max_model_len == 4352 and\n",
        "summary graph identity",
    )
    text = replace_once(
        text,
        '         .identity.profiler == "torch_xpu_report_only" and\n         .identity.profile_delay_iterations == 65 and\n         .identity.profile_max_iterations == 4 and\n',
        f'         .identity.libccl_sha256 == "{LIBCCL_SHA256}" and\n'
        f'         .identity.ccl_kernel_sha256 == "{CCL_KERNEL_SHA256}" and\n',
        "summary profiler removal",
    )
    text = replace_once(
        text,
        '       jq -e \'.status == "passed" and .recovery_canary == "passed" and\n',
        '       jq -e \'.status == "passed" and .phase == "after" and\n'
        "         .size_1_full_dispatch_count > 0 and\n"
        "         (.collective_processes | length) >= 4 and\n"
        f'         .libccl.sha256 == "{LIBCCL_SHA256}" and\n'
        f'         .ccl_kernel.sha256 == "{CCL_KERNEL_SHA256}" and\n'
        "         .torchinductor_files == []' \\\n"
        '         "${run_dir}/fullgraph-runtime-after.json" >/dev/null 2>&1 && \\\n'
        '       jq -e \'.status == "passed" and .recovery_canary == "passed" and\n',
        "supervisor runtime graph gate",
    )
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("launcher", "client", "supervisor"))
    parser.add_argument("--derived-hash", default="A33_DERIVED_HASH")
    parser.add_argument("--runtime-verifier-hash", default="RUNTIME_VERIFIER_HASH")
    parser.add_argument("--wrapper-hash", default="A33_WRAPPER_HASH")
    parser.add_argument("--client-hash", default="A33_CLIENT_HASH")
    args = parser.parse_args()
    text = sys.stdin.read()
    if args.mode == "launcher":
        output = launcher(text, args.derived_hash)
    elif args.mode == "client":
        output = client(text, args.runtime_verifier_hash)
    else:
        output = supervisor(text, args.wrapper_hash, args.client_hash)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
