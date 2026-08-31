#!/usr/bin/env python3
"""Bind A30's generated launcher to the qualified hybrid serving stage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys


INPUT_SHA256 = "26f31630ecb33327609f30a5156ecf30d9be9980613cbfbbdd8e2d0560793d63"
OUTPUT_SHA256 = "8733a114124632c3fe47edaefac261f57e4999d1af211152f79a0ca8a29758f0"
VLLM_HEAD = "797769b34b6db5c934609b75dc04cc61ec66e5f9"
KERNEL_HEAD = "eeee7d671abfa964626baa18da2174bb92cac80a"
KERNEL_CHAIN = "\n".join(
    (
        KERNEL_HEAD,
        "042c6e877b667f03087091ce3ab58b80903afc20",
        "a6ee94fd8fadb97dc033921f1019ef18f14d5dd0",
        "359466a262489bdf4e1774e3572202dc82a00718",
        "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
    )
)
STAGE = "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2"
STAGE_MANIFEST = f"{STAGE}-evidence/runtime-stage.sha256"
FINALIZER_MANIFEST = f"{STAGE}-evidence/finalizer-evidence.sha256"
QUALIFICATION = (
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "grouped-serving-stage-eeee7d6-a2-qualification-a4/"
    "qualification-evidence.sha256"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace(source: str, old: str, new: str, count: int = 1) -> str:
    actual = source.count(old)
    if actual != count:
        raise SystemExit(f"FAIL: A30 anchor count {actual}, expected {count}: {old}")
    return source.replace(old, new)


def transform(source: str) -> str:
    source = replace(
        source,
        'stage="${KERNEL_STAGE:-/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70}"',
        f'stage="${{KERNEL_STAGE:-{STAGE}}}"',
    )
    source = replace(
        source,
        'runtime_manifest="${repo_root}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"',
        f'runtime_manifest="{STAGE_MANIFEST}"',
    )
    source = replace(
        source,
        'expected_kernels_head="ad25aa9f69a2171612b9c6b83dfa82c69559f9e4"',
        f'expected_kernels_head="{KERNEL_HEAD}"',
        count=2,
    )
    source = replace(
        source,
        'expected_stage_build_head="ad25aa9f69a2171612b9c6b83dfa82c69559f9e4"',
        f'expected_stage_build_head="{KERNEL_HEAD}"',
    )
    source = replace(
        source,
        'expected_stage_build_head="2f829747503c77d4814834dffd0840fb1dd9f75a"',
        f'expected_stage_build_head="{KERNEL_HEAD}"',
    )
    source = replace(
        source,
        'padding_receipt="${repo_root}/experiments/qwen38-flash-next-fp8-b70/data/20260827-moe-padding-guard-gates.json"',
        "\n".join(
            (
                'padding_receipt="${repo_root}/experiments/qwen38-flash-next-fp8-b70/data/20260827-moe-padding-guard-gates.json"',
                f'stage_finalizer_manifest="{FINALIZER_MANIFEST}"',
                f'stage_qualification_manifest="{QUALIFICATION}"',
            )
        ),
    )
    source = replace(
        source,
        '[[ -f "${runtime_manifest}" && -f "${validation_root}/summary.json" && -f "${moe_receipt}" && -f "${padding_receipt}" ]] || fail "sealed validation input is missing"',
        "\n".join(
            (
                '[[ -f "${runtime_manifest}" && -f "${validation_root}/summary.json" && -f "${moe_receipt}" && -f "${padding_receipt}" ]] || fail "sealed validation input is missing"',
                '[[ -f "${stage_finalizer_manifest}" && -f "${stage_qualification_manifest}" ]] || fail "qualified hybrid-stage evidence is missing"',
                '[[ "$(sha256sum "${runtime_manifest}" | cut -d\' \' -f1)" == a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d ]] || fail "hybrid stage manifest changed"',
                '[[ "$(sha256sum "${stage_finalizer_manifest}" | cut -d\' \' -f1)" == 2c049273bfc9e8dd429e2f74969cb9c4917a6e23833fcb8e8584ba8944a62aee ]] || fail "hybrid finalizer evidence changed"',
                '[[ "$(sha256sum "${stage_qualification_manifest}" | cut -d\' \' -f1)" == ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591 ]] || fail "A4 qualification evidence changed"',
                '(cd /home/steve/llm-optimizations && sha256sum -c "${stage_finalizer_manifest}") >/dev/null || fail "hybrid finalizer evidence closure failed"',
                'sha256sum -c "${stage_qualification_manifest}" >/dev/null || fail "A4 qualification evidence closure failed"',
            )
        ),
    )
    source = replace(
        source,
        '[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == "${expected_kernels_head}" ]] || fail "kernel overlay head changed"',
        "\n".join(
            (
                '[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == "${expected_kernels_head}" ]] || fail "kernel workspace head changed"',
                f'[[ "$(git -C "${{kernels_src}}" rev-list --max-count=5 HEAD)" == $\'{KERNEL_CHAIN}\' ]] || fail "kernel workspace chain changed"',
            )
        ),
    )
    source = replace(
        source,
        '[[ -z "$(git -C "${kernels_src}" status --porcelain --untracked-files=no)" ]] || fail "kernel overlay has tracked modifications"',
        "\n".join(
            (
                '[[ -z "$(git -C "${kernels_src}" status --porcelain --untracked-files=no)" ]] || fail "kernel workspace has tracked modifications"',
                '[[ "$(git -C "${kernels_src}" status --porcelain)" == "?? third_party/" ]] || fail "kernel workspace untracked state changed"',
            )
        ),
    )
    source = replace(
        source,
        "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1",
        "\n".join(
            (
                "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1",
                "export VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP=1",
            )
        ),
    )
    source = replace(
        source,
        "assert envs.VLLM_KV_CACHE_LAYOUT == 'BLHNC'",
        "\n".join(
            (
                "assert envs.VLLM_KV_CACHE_LAYOUT == 'BLHNC'",
                "assert envs.VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP is True",
                "grouped_schema = torch.ops._xpu_C.cutlass_grouped_gemm_interface.default._schema",
                "assert len(grouped_schema.arguments) == 11, grouped_schema",
                "print(grouped_schema)",
            )
        ),
    )
    source = replace(
        source,
        "assert config.scheduler_config.max_num_batched_tokens == 64",
        "\n".join(
            (
                "assert config.scheduler_config.max_num_batched_tokens == 64",
                "assert config.scheduler_config.max_num_seqs == 1",
                "assert config.scheduler_config.max_num_scheduled_tokens is None",
                "assert config.model_config.enforce_eager is True",
                "assert config.compilation_config.cudagraph_mode.name == 'NONE'",
            )
        ),
    )
    source = replace(
        source,
        "  printf 'runtime_stage_build_head=%s\\n' \"${expected_stage_build_head}\"",
        "\n".join(
            (
                "  printf 'runtime_stage_native_head=%s\\n' \"${expected_stage_build_head}\"",
                "  printf 'runtime_stage_retained_base_head=2f829747503c77d4814834dffd0840fb1dd9f75a\\n'",
                "  printf 'runtime_stage_manifest_sha256=a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d\\n'",
                "  printf 'runtime_stage_qualification_sha256=ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591\\n'",
                "  printf 'hc_grouped_up=1\\n'",
            )
        ),
    )
    source = replace(
        source,
        'setsid "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1 &',
        "\n".join(
            (
                f'[[ "$(git -C "${{vllm_src}}" rev-parse HEAD)" == "{VLLM_HEAD}" ]] || fail "vLLM source changed immediately before launch"',
                '[[ -z "$(git -C "${vllm_src}" status --porcelain)" ]] || fail "vLLM source became dirty immediately before launch"',
                f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD)" == "{KERNEL_HEAD}" ]] || fail "kernel source changed immediately before launch"',
                f'[[ "$(git -C "${{kernels_src}}" rev-list --max-count=5 HEAD)" == $\'{KERNEL_CHAIN}\' ]] || fail "kernel chain changed immediately before launch"',
                '[[ -z "$(git -C "${kernels_src}" status --porcelain --untracked-files=no)" ]] || fail "kernel source became dirty immediately before launch"',
                '[[ "$(git -C "${kernels_src}" status --porcelain)" == "?? third_party/" ]] || fail "kernel untracked state changed immediately before launch"',
                '[[ "$(sha256sum "${vllm_src}/vllm/models/qwen4_exp/amd/low_latency_gemm.py" | cut -d\' \' -f1)" == 5d9f99945f2f01396afdece710e69b719139bf57fb2232cb831b467b8f64737f ]] || fail "HC grouped source changed immediately before launch"',
                '[[ "$(sha256sum "${vllm_src}/vllm/envs.py" | cut -d\' \' -f1)" == 5dda238b194947d046169c9a0f9bead7f30c420b6943cdd8d1b15291dfa99906 ]] || fail "HC environment contract changed immediately before launch"',
                'setsid "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1 &',
            )
        ),
    )
    return source


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: rewrite-a30-hybrid-stage-contract.py PATH")
    path = Path(sys.argv[1])
    original = path.read_bytes()
    actual_input = digest(original)
    if actual_input != INPUT_SHA256:
        raise SystemExit(
            f"FAIL: A30 generated input is {actual_input}, expected {INPUT_SHA256}"
        )
    transformed = transform(original.decode("utf-8")).encode("utf-8")
    actual_output = digest(transformed)
    if actual_output != OUTPUT_SHA256:
        raise SystemExit(
            f"FAIL: A30 generated output is {actual_output}, expected {OUTPUT_SHA256}"
        )
    temporary = path.with_name(f"{path.name}.a30.{os.getpid()}")
    temporary.write_bytes(transformed)
    os.chmod(temporary, 0o700)
    os.replace(temporary, path)


if __name__ == "__main__":
    main()
