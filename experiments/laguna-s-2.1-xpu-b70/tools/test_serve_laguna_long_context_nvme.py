#!/usr/bin/env python3
"""Host-only guard tests for the long-context launcher's depth-sweep profile.

The launcher is copied byte-identically beside a stub of the NVMe path module,
so the real guard code runs while every device, model, and service side effect
is replaced by a temporary directory and a recording ``vllm`` shim. Nothing
here starts a service or touches the NVMe lane.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


LAUNCHER = Path(__file__).resolve().parent / "serve_laguna_long_context_nvme.sh"
NVME_STUB = """#!/usr/bin/env bash
LAGUNA_NVME_MODEL_ROOT="$LAGUNA_TEST_SANDBOX/model"
LAGUNA_NVME_TARGET_ROOT="$LAGUNA_NVME_MODEL_ROOT/int4"
LAGUNA_NVME_DRAFT_ROOT="$LAGUNA_NVME_MODEL_ROOT/dflash-int4"
LAGUNA_NVME_ARTIFACT_ROOT="$LAGUNA_TEST_SANDBOX/artifacts"
LAGUNA_NVME_RUN_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT/runs"
laguna_nvme_prepare_paths() { :; }
laguna_nvme_assert_fixed_path() { :; }
"""
VLLM_SHIM = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$LAGUNA_TEST_SANDBOX/vllm-argv.txt"
exit 0
"""

SHARED_CANDIDATE_ENV = {
    name: "1"
    for name in (
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH",
        "VLLM_USE_BREAKABLE_CUDAGRAPH",
        "XPU_GRAPH",
        "VLLM_XPU_ENABLE_XPU_GRAPH",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE",
        "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE",
    )
}
QDEPTH_DISABLED_ENV = {
    name: "0"
    for name in (
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
        "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK",
        "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
        "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16",
        "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8",
        "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH",
        "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS",
        "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE",
        "VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD",
        "VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS",
        "VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE",
        "VLLM_XPU_LAGUNA_DECODE_GRF128",
        "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES",
    )
}
# 8182 + (depth - 1) keeps the derived per-step budget at 8182 for every depth.
PINNED_BATCHED_TOKENS = {11: "8192", 7: "8188", 3: "8184", 1: "8182"}


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    run_dir = tmp_path / "artifacts" / "runs" / "arm"
    run_dir.mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    shim = tmp_path / "bin" / "vllm"
    shim.write_text(VLLM_SHIM, encoding="utf-8")
    shim.chmod(0o755)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "laguna_nvme_paths.sh").write_text(
        NVME_STUB, encoding="utf-8"
    )
    shutil.copyfile(LAUNCHER, tmp_path / "tools" / LAUNCHER.name)
    (tmp_path / "tools" / LAUNCHER.name).chmod(0o755)
    return tmp_path


def launch(
    sandbox: Path,
    *,
    depth: int | None = 11,
    batched: str | None = None,
    profile: str = "qdepth",
    overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": f"{sandbox / 'bin'}:/usr/bin:/bin",
        "LAGUNA_TEST_SANDBOX": str(sandbox),
        "LAGUNA_LONG_CANDIDATE_PROFILE": profile,
        "VLLM_USE_AOT_COMPILE": "0",
        **SHARED_CANDIDATE_ENV,
        **QDEPTH_DISABLED_ENV,
    }
    if depth is not None:
        environment.update(
            {
                "LAGUNA_SPEC": str(depth),
                "LAGUNA_M": str(depth + 1),
                "VLLM_XPU_LAGUNA_EXACT_MAX_M": str(depth + 1),
                "LAGUNA_MAX_NUM_BATCHED_TOKENS": (
                    PINNED_BATCHED_TOKENS[depth] if batched is None else batched
                ),
            }
        )
    elif batched is not None:
        environment["LAGUNA_MAX_NUM_BATCHED_TOKENS"] = batched
    environment.update(overrides or {})
    return subprocess.run(
        [
            str(sandbox / "tools" / LAUNCHER.name),
            "candidate",
            str(sandbox / "artifacts" / "runs" / "arm"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_incumbent_depth_launches_with_the_incumbent_budget(sandbox: Path) -> None:
    result = launch(sandbox, depth=11)

    assert result.returncode == 0, result.stderr
    argv = (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--max-num-batched-tokens" in argv
    assert argv[argv.index("--max-num-batched-tokens") + 1] == "8192"
    assert "--max-num-scheduled-tokens" not in argv
    assert '"num_speculative_tokens":11' in "".join(argv)
    assert '"cudagraph_capture_sizes":[12]' in "".join(argv)
    assert "depth=11 width=12 batched=8192 derived_scheduled=8182" in result.stderr


def test_depth_seven_pins_the_budget_to_the_same_derived_partition(
    sandbox: Path,
) -> None:
    result = launch(sandbox, depth=7)

    assert result.returncode == 0, result.stderr
    argv = (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--max-num-batched-tokens") + 1] == "8188"
    assert '"num_speculative_tokens":7' in "".join(argv)
    assert '"cudagraph_capture_sizes":[8]' in "".join(argv)
    assert "depth=7 width=8 batched=8188 derived_scheduled=8182" in result.stderr


@pytest.mark.parametrize("depth", [11, 7])
def test_unpinned_budget_fails_before_launch(sandbox: Path, depth: int) -> None:
    # 8192 is the incumbent budget and is always accepted by the allowlist, so
    # at depth 7 it is the realistic way to derive the wrong partition.
    result = launch(sandbox, depth=depth, batched="16384" if depth == 11 else "8192")

    assert result.returncode == 2
    assert "derives max_num_scheduled_tokens=" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize("depth", [3, 1])
def test_widths_without_a_fused_target_path_are_refused(
    sandbox: Path, depth: int
) -> None:
    result = launch(sandbox, depth=depth)

    assert result.returncode == 2
    assert "not cleanly measurable" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"VLLM_XPU_LAGUNA_EXACT_MAX_M": "8"}, "EXACT_MAX_M to equal LAGUNA_M"),
        ({"LAGUNA_M": "13"}, "LAGUNA_M to be LAGUNA_SPEC plus one"),
        (
            {"VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE": "1"},
            "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE must be zero",
        ),
        (
            {"VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK": "1"},
            "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK must be zero",
        ),
        (
            {"VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE": "1"},
            "VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE must be zero",
        ),
        (
            {"VLLM_XPU_LAGUNA_DECODE_GRF128": "1"},
            "VLLM_XPU_LAGUNA_DECODE_GRF128 must be zero",
        ),
        ({"LAGUNA_SPEC": "9", "LAGUNA_M": "10"}, "LAGUNA_SPEC=11 or LAGUNA_SPEC=7"),
    ],
)
def test_selector_drift_fails_closed(
    sandbox: Path, overrides: dict[str, str], message: str
) -> None:
    result = launch(sandbox, depth=11, overrides=overrides)

    assert result.returncode == 2
    assert message in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_qdepth_cannot_claim_the_closed_alignment_budget(sandbox: Path) -> None:
    result = launch(
        sandbox,
        depth=11,
        batched="8202",
        overrides={"LAGUNA_MAX_NUM_SCHEDULED_TOKENS": "8192"},
    )

    assert result.returncode == 2
    assert "requires q12 exact-prefill candidate" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize("batched", ["8184", "8188"])
def test_offstride_budget_is_reserved_for_qdepth(sandbox: Path, batched: str) -> None:
    result = launch(sandbox, depth=11, batched=batched, profile="q12")

    assert result.returncode == 2
    assert "reserved for the qdepth depth-sweep candidate" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_partition_aligned_budget_is_refused_to_other_candidates(
    sandbox: Path,
) -> None:
    result = launch(sandbox, depth=11, batched="8182", profile="q12")

    assert result.returncode == 2
    assert "qdepth candidate and the partition-aligned teacher" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_speculation_off_teacher_may_pin_the_candidate_partition(
    sandbox: Path,
) -> None:
    # With no speculative config the derived budget is never computed and the
    # scheduler falls back to the batched budget, so 8182 is what reproduces
    # the candidate's 8182/8094 partition on the canonical q=1 identity.
    result = subprocess.run(
        [
            str(sandbox / "tools" / LAUNCHER.name),
            "teacher",
            str(sandbox / "artifacts" / "runs" / "arm"),
        ],
        env={
            "PATH": f"{sandbox / 'bin'}:/usr/bin:/bin",
            "LAGUNA_TEST_SANDBOX": str(sandbox),
            "LAGUNA_MAX_NUM_BATCHED_TOKENS": "8182",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    argv = (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--max-num-batched-tokens") + 1] == "8182"
    assert "--enforce-eager" in argv
    assert "--speculative-config" not in argv


def test_existing_q12_profile_is_undisturbed(sandbox: Path) -> None:
    q12_env = {
        name: "1"
        for name in (
            "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16",
            "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH",
            "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS",
            "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE",
            "VLLM_XPU_LAGUNA_DECODE_GRF128",
            "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES",
        )
    }
    q12_env.update(
        {
            "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "0",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8": "0",
        }
    )
    result = launch(sandbox, depth=11, batched="8192", profile="q12", overrides=q12_env)

    assert result.returncode == 0, result.stderr
    argv = (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--max-num-batched-tokens") + 1] == "8192"
    assert '"cudagraph_capture_sizes":[12]' in "".join(argv)
    assert "qdepth" not in result.stderr


def test_q12_context_cutoff_captures_m1_and_m12(sandbox: Path) -> None:
    q12_env = {
        name: "1"
        for name in (
            "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16",
            "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH",
            "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS",
            "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE",
            "VLLM_XPU_LAGUNA_DECODE_GRF128",
            "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES",
        )
    }
    q12_env.update(
        {
            "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "0",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8": "0",
            "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_CUTOFF": "8192",
        }
    )

    result = launch(
        sandbox,
        depth=11,
        batched="8192",
        profile="q12",
        overrides=q12_env,
    )

    assert result.returncode == 0, result.stderr
    argv = (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()
    joined = "".join(argv)
    assert '"cudagraph_capture_sizes":[1,12]' in joined
    assert '"max_cudagraph_capture_size":12' in joined
    assert '"num_speculative_tokens":11' in joined


def test_q12_context_cutoff_rejects_replay_diagnostics(sandbox: Path) -> None:
    q12_env = {
        name: "1"
        for name in (
            "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK",
            "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16",
            "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH",
            "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS",
            "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE",
            "VLLM_XPU_LAGUNA_DECODE_GRF128",
            "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES",
        )
    }
    q12_env.update(
        {
            "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "0",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8": "0",
            "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_CUTOFF": "8192",
            "LAGUNA_PROFILE_DIR": "/tmp/diagnostic",
        }
    )

    result = launch(
        sandbox,
        depth=11,
        batched="8192",
        profile="q12",
        overrides=q12_env,
    )

    assert result.returncode == 2
    assert "rejects replay diagnostics" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_unknown_profile_names_the_supported_set(sandbox: Path) -> None:
    result = launch(sandbox, depth=11, batched="8192", profile="q4")

    assert result.returncode == 2
    assert "must be q12, q8, q8fp8, or qdepth" in result.stderr
