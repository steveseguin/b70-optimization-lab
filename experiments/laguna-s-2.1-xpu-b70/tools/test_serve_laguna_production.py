#!/usr/bin/env python3
"""Host-only guard tests for the production launcher.

The launcher is copied byte-identically beside a stub of the NVMe path module,
a recording ``vllm`` shim, and a synthetic ``meminfo`` file, so the real guard
code runs while every device, model, and service side effect is replaced. The
host-memory guard is exercised against the synthetic file rather than the live
one, so the swap hazard is tested without ever creating it.

Nothing here starts a service, loads a model, touches the NVMe lane, or reaches
an XPU.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


LAUNCHER = Path(__file__).resolve().parent / "serve_laguna_production.sh"
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
# Comfortably above both floors: 32 GiB available RAM, 20 GiB free swap.
HEALTHY_MEMINFO = "MemAvailable:   33554432 kB\nSwapFree:       20971520 kB\n"

SEALED_ENV = {
    name: "1"
    for name in (
        "VLLM_XPU_EXACT_SPEC_ATTN",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH",
        "VLLM_USE_BREAKABLE_CUDAGRAPH",
        "XPU_GRAPH",
        "VLLM_XPU_ENABLE_XPU_GRAPH",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE",
        "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE",
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
SEALED_ENV.update(
    {
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "0",
        "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8": "0",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "LAGUNA_M": "12",
        "LAGUNA_SPEC": "11",
        "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    }
)

# Every selector the launcher classifies BATCH-HOSTILE, with the substring its
# refusal must contain. The silent-fallback ones are the point of the exercise:
# at batch > 1 they do not fail, they quietly stop firing.
BATCH_HOSTILE_CASES = [
    ("VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH", "requires max_num_seqs == 1"),
    ("VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA", "M8_BREAKABLE_GRAPH"),
    ("VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE", "literal batch term"),
    ("VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16", "inherits the DFlash context-KV contract"),
    ("VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS", "requires max_num_seqs == 1"),
    ("VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE", "requires max_num_seqs == 1"),
    ("VLLM_XPU_LAGUNA_M8_QKNORM_ROPE", "SILENTLY"),
    ("VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE", "SILENTLY"),
    ("VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE", "SILENTLY"),
    ("VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE", "per-row Python loop"),
    ("VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK", "silently bypassed"),
    ("VLLM_XPU_EXACT_SPEC_ATTN", "slower than plain batched execution"),
    ("VLLM_XPU_PERSISTENT_KSTEP_DECODE", "requires max_num_seqs=1"),
    ("VLLM_XPU_LAGUNA_DECODE_GRF128", "total_m == 120"),
    ("VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED", "downstream of the GRF128"),
    ("VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES", "cannot fire"),
    ("VLLM_XPU_LAGUNA_M8_REMOTE_ZERO", "1 <= num_rows <= 8"),
    ("VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION", "no else and no raise"),
    ("VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE", "SILENTLY skipped"),
    ("VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2", "max_num_seqs == 1"),
    ("VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE", "max_num_seqs == 1"),
    ("VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM", "stride-zero bmm"),
]


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
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
    (tmp_path / "meminfo").write_text(HEALTHY_MEMINFO, encoding="utf-8")
    return tmp_path


def launch(
    sandbox: Path,
    *,
    profile: str = "sealed-single-stream",
    overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": f"{sandbox / 'bin'}:/usr/bin:/bin",
        "LAGUNA_TEST_SANDBOX": str(sandbox),
        "LAGUNA_PRODUCTION_PROFILE": profile,
        "LAGUNA_PRODUCTION_MEMINFO": str(sandbox / "meminfo"),
    }
    if profile == "sealed-single-stream":
        environment.update(SEALED_ENV)
    environment.update(overrides or {})
    return subprocess.run(
        [str(sandbox / "tools" / LAUNCHER.name)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )


def argv_of(sandbox: Path) -> list[str]:
    return (sandbox / "vllm-argv.txt").read_text(encoding="utf-8").splitlines()


def test_sealed_profile_launches_the_record_identity(sandbox: Path) -> None:
    result = launch(sandbox)

    assert result.returncode == 0, result.stderr
    argv = argv_of(sandbox)
    assert argv[argv.index("--max-num-seqs") + 1] == "1"
    assert argv[argv.index("--gpu-memory-utilization") + 1] == "0.80"
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert '"num_speculative_tokens":11' in "".join(argv)
    assert '"cudagraph_capture_sizes":[12]' in "".join(argv)
    assert "--api-key" not in argv
    assert "profile=sealed-single-stream" in result.stderr


def test_sealed_profile_refuses_concurrency(sandbox: Path) -> None:
    result = launch(sandbox, overrides={"LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2"})

    assert result.returncode == 2
    assert "requires \\\nLAGUNA_PRODUCTION_MAX_NUM_SEQS=1" in result.stderr or (
        "LAGUNA_PRODUCTION_MAX_NUM_SEQS=1" in result.stderr
    )
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize(
    "missing",
    [
        "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE",
        "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH",
        "VLLM_XPU_LAGUNA_DECODE_GRF128",
        "VLLM_XPU_EXACT_SPEC_ATTN",
    ],
)
def test_sealed_profile_requires_each_record_selector(
    sandbox: Path, missing: str
) -> None:
    result = launch(sandbox, overrides={missing: "0"})

    assert result.returncode == 2
    assert f"{missing} must be explicitly set to 1" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_concurrent_profile_launches_within_the_measured_ceiling(
    sandbox: Path,
) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={"LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2"},
    )

    assert result.returncode == 0, result.stderr
    argv = argv_of(sandbox)
    assert argv[argv.index("--max-num-seqs") + 1] == "2"
    assert "--speculative-config" not in argv
    assert "--enforce-eager" in argv
    assert "never been measured" in result.stderr


@pytest.mark.parametrize(("selector", "message"), BATCH_HOSTILE_CASES)
def test_batch_hostile_selectors_are_refused_by_name(
    sandbox: Path, selector: str, message: str
) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={
            "LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2",
            selector: "1",
        },
    )

    assert result.returncode == 2
    assert selector in result.stderr
    assert message in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize(
    "selector",
    [
        "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS",
        "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP",
    ],
)
def test_unknown_batch_behaviour_is_refused_concurrently(
    sandbox: Path, selector: str
) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={"LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2", selector: "1"},
    )

    assert result.returncode == 2
    assert selector in result.stderr
    assert "UNKNOWN batch behaviour" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_batch_safe_replicated_embedding_survives_concurrency(
    sandbox: Path,
) -> None:
    # It carries no batch or row term anywhere, so the concurrent profile must
    # not refuse it. This is the one core selector that crosses the boundary.
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={
            "LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2",
            "VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING": "1",
        },
    )

    assert result.returncode == 0, result.stderr


def test_deterministic_graph_is_refused_for_its_own_reason(sandbox: Path) -> None:
    result = launch(sandbox, overrides={"VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "1"})

    assert result.returncode == 2
    assert "carries no batch constraint" in result.stderr
    assert "not for batch behaviour" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


@pytest.mark.parametrize("util", ["0.90", "0.85", "0.81"])
def test_utilization_above_the_measured_ceiling_is_refused(
    sandbox: Path, util: str
) -> None:
    result = launch(sandbox, overrides={"LAGUNA_PRODUCTION_GPU_UTIL": util})

    assert result.returncode == 2
    assert "exceeds the measured safe ceiling of 0.80" in result.stderr
    assert "took the host down" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_kv_ceiling_refuses_a_third_full_length_sequence(sandbox: Path) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={"LAGUNA_PRODUCTION_MAX_NUM_SEQS": "3"},
    )

    assert result.returncode == 2
    assert "needs 98304 KV tokens" in result.stderr
    assert "91258" in result.stderr
    assert "fits 2 concurrent full-length requests, not 3" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_shorter_requests_buy_more_concurrency(sandbox: Path) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={
            "LAGUNA_PRODUCTION_MAX_NUM_SEQS": "8",
            "LAGUNA_PRODUCTION_MAX_MODEL_LEN": "8192",
        },
    )

    assert result.returncode == 0, result.stderr
    argv = argv_of(sandbox)
    assert argv[argv.index("--max-num-seqs") + 1] == "8"
    assert argv[argv.index("--max-model-len") + 1] == "8192"


def test_low_available_ram_stops_before_the_model(sandbox: Path) -> None:
    (sandbox / "meminfo").write_text(
        "MemAvailable:    8388608 kB\nSwapFree:       20971520 kB\n",
        encoding="utf-8",
    )
    result = launch(sandbox)

    assert result.returncode == 2
    assert "below the unconditional floor" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_the_host_oom_memory_combination_is_refused(sandbox: Path) -> None:
    # 14 GiB available RAM with under 1 GiB free swap is the shape the host was
    # in immediately before the 2026-08-02 OOM.
    (sandbox / "meminfo").write_text(
        "MemAvailable:   14680064 kB\nSwapFree:         984824 kB\n",
        encoding="utf-8",
    )
    result = launch(sandbox)

    assert result.returncode == 2
    assert "preceded the 2026-08-02 host OOM" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_low_swap_alone_is_survivable_with_ample_ram(sandbox: Path) -> None:
    (sandbox / "meminfo").write_text(
        "MemAvailable:   33554432 kB\nSwapFree:         984824 kB\n",
        encoding="utf-8",
    )
    result = launch(sandbox)

    assert result.returncode == 0, result.stderr


def test_non_loopback_bind_is_refused_without_acknowledgement(
    sandbox: Path,
) -> None:
    result = launch(sandbox, overrides={"LAGUNA_PRODUCTION_HOST": "0.0.0.0"})

    assert result.returncode == 2
    assert "unauthenticated by default" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_acknowledged_lan_bind_still_requires_a_key(sandbox: Path) -> None:
    result = launch(
        sandbox,
        overrides={
            "LAGUNA_PRODUCTION_HOST": "0.0.0.0",
            "LAGUNA_PRODUCTION_LAN_ACK": "1",
        },
    )

    assert result.returncode == 2
    assert "requires LAGUNA_PRODUCTION_API_KEY_FILE" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_a_world_readable_key_file_is_refused(sandbox: Path) -> None:
    key_file = sandbox / "api-key"
    key_file.write_text("k" * 40, encoding="utf-8")
    key_file.chmod(0o644)
    result = launch(
        sandbox,
        overrides={
            "LAGUNA_PRODUCTION_HOST": "0.0.0.0",
            "LAGUNA_PRODUCTION_LAN_ACK": "1",
            "LAGUNA_PRODUCTION_API_KEY_FILE": str(key_file),
        },
    )

    assert result.returncode == 2
    assert "must be mode 600 or 400" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_a_short_key_is_refused(sandbox: Path) -> None:
    key_file = sandbox / "api-key"
    key_file.write_text("tooshort", encoding="utf-8")
    key_file.chmod(0o600)
    result = launch(
        sandbox,
        overrides={
            "LAGUNA_PRODUCTION_HOST": "0.0.0.0",
            "LAGUNA_PRODUCTION_LAN_ACK": "1",
            "LAGUNA_PRODUCTION_API_KEY_FILE": str(key_file),
        },
    )

    assert result.returncode == 2
    assert "at least 32 characters" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_an_acknowledged_keyed_lan_bind_passes_the_key(sandbox: Path) -> None:
    key_file = sandbox / "api-key"
    key_file.write_text("k" * 40 + "\n", encoding="utf-8")
    key_file.chmod(0o600)
    result = launch(
        sandbox,
        overrides={
            "LAGUNA_PRODUCTION_HOST": "0.0.0.0",
            "LAGUNA_PRODUCTION_LAN_ACK": "1",
            "LAGUNA_PRODUCTION_API_KEY_FILE": str(key_file),
        },
    )

    assert result.returncode == 0, result.stderr
    argv = argv_of(sandbox)
    assert argv[argv.index("--api-key") + 1] == "k" * 40
    assert argv[argv.index("--host") + 1] == "0.0.0.0"


@pytest.mark.parametrize(
    "selector",
    [
        "VLLM_XPU_LAGUNA_PARITY_PROBE",
        "VLLM_XPU_LAGUNA_DRAFT_IDENTITY_PROBE",
        "VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_DEVICE_CYCLES",
    ],
)
def test_diagnostic_selectors_are_refused_in_production(
    sandbox: Path, selector: str
) -> None:
    result = launch(sandbox, overrides={selector: "1"})

    assert result.returncode == 2
    assert "diagnostic selector" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_trace_roots_must_be_unset(sandbox: Path) -> None:
    result = launch(
        sandbox, overrides={"VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION": "anything"}
    )

    assert result.returncode == 2
    assert "must be unset in a production service" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_concurrent_profile_refuses_a_single_sequence(sandbox: Path) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={"LAGUNA_PRODUCTION_MAX_NUM_SEQS": "1"},
    )

    assert result.returncode == 2
    assert "cost \\\nfor none of its benefit" in result.stderr or (
        "none of its benefit" in result.stderr
    )
    assert not (sandbox / "vllm-argv.txt").exists()


def test_concurrent_speculation_is_refused(sandbox: Path) -> None:
    result = launch(
        sandbox,
        profile="concurrent",
        overrides={
            "LAGUNA_PRODUCTION_MAX_NUM_SEQS": "2",
            "LAGUNA_PRODUCTION_CONCURRENT_SPECULATION": "1",
        },
    )

    assert result.returncode == 2
    assert "never been measured" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()


def test_unknown_profile_names_the_supported_set(sandbox: Path) -> None:
    result = launch(sandbox, profile="fast")

    assert result.returncode == 2
    assert "must be sealed-single-stream or concurrent" in result.stderr
    assert not (sandbox / "vllm-argv.txt").exists()
