#!/usr/bin/env python3
"""CPU-only launch-contract checks for the HC gate-mix A1 runner."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


RUNNER = Path(__file__).with_name("run-q38-hc-gate-mix-exact-staged-a1.sh")
RESULT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/"
    "20260901-hc-gate-mix-exact-staged-a1"
)
STAGE = RESULT.with_name(RESULT.name + ".staging")
CACHE = Path("/dev/shm/q38-hc-gate-mix-exact-staged-a1")


def source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_binds_candidate_authority_and_runtime_identity() -> None:
    text = source()
    assert "expected_gate=3af1fd48b573cbb1" in text
    assert "expected_core=02989e1fc50b3c95" in text
    assert "expected_vllm=cbc3cb588a7cae8d" in text
    assert "expected_authority=a2ed67ce6240a150" in text
    assert "expected_python=202c17d1671602a4e" in text
    assert "expected_python_version=3.12.13" in text
    assert "expected_torch_version=2.11.0+xpu" in text
    assert "expected_torch_git=70d99e998b4955e0" in text
    assert "expected_torch_xpu=20250302" in text
    assert "expected_clearance_validator=2293b3588a275e15" in text
    assert "expected_publisher=fc8cf0244f091ce8" in text
    assert 'git -C "$vllm" status --porcelain --untracked-files=no' in text


def test_clearance_precedes_any_result_or_cache_creation() -> None:
    text = source()
    clearance = text.index('"$clearance_validator" --clearance-json "$clearance"')
    result = text.index('mkdir "$result"')
    cache = text.index('mkdir -m 0700 "$cache_root"')
    assert clearance < result < cache
    assert '[[ -f "$clearance" && ! -L "$clearance" ]]' in text
    assert 'install -m 0444 "$clearance" "${result}/clearance.json.tmp"' in text


def test_runner_requires_external_evidence_and_exclusive_paths() -> None:
    text = source()
    assert '"$evidence_source" == /dev/sda2' in text
    assert '"$evidence_type" == fuseblk' in text
    assert '"$evidence_target" == /mnt/usb-models' in text
    assert '[[ ! -e "$result" && ! -L "$result" ]]' in text
    assert '[[ ! -e "$result_final" && ! -L "$result_final" ]]' in text
    assert '[[ ! -e "$cache_root" && ! -L "$cache_root" ]]' in text
    assert "flock -n 7" in text and "flock -n 8" in text and "flock -n 9" in text
    assert '[[ -z "$(active_runtime_processes)" ]]' in text


def test_selector_exposes_exactly_one_named_b70() -> None:
    text = source()
    assert "ONEAPI_DEVICE_SELECTOR=level_zero:0" in text
    assert "ZE_AFFINITY_MASK" not in text
    assert "torch.xpu.device_count()" in text
    assert "count != 1" in text
    assert 'name != "Intel(R) Arc(TM) Pro B70 Graphics"' in text
    assert ".visible_xpu_count == 1" in text
    assert "0000:23:00.0" in text and "0000:47:00.0" in text


def test_exactly_one_owned_c_a_a_c_gate_is_invoked() -> None:
    text = source()
    invocation = '"$python" "$staged_gate" >"${result}/gate-result.json.tmp"'
    assert text.count(invocation) == 1
    assert "setsid timeout --signal=TERM --kill-after=30s 1200s env -i" in text
    assert '.timing.order == ["control", "candidate", "candidate", "control"]' in text
    assert "timing_order=control,candidate,candidate,control" in text
    assert "gate_invocations=1" in text


def test_runner_continuously_aborts_only_its_owned_group_on_aer_change() -> None:
    text = source()
    assert 'pgid=$(ps -o pgid= -p "$leader"' in text
    assert '[[ "$pgid" == "$leader" ]]' in text
    assert 'kill -TERM -- "-${active_pgid}"' in text
    assert 'kill -KILL -- "-${active_pgid}"' in text
    assert 'while kill -0 "$leader"' in text
    assert "sleep 1" in text
    assert '"$nvme_now" != "$nvme_aer_baseline"' in text
    assert '"$root_now" != "$root_aer_baseline"' in text
    assert "trap finalize EXIT" in text


def test_live_sources_and_clearance_are_staged_and_revalidated() -> None:
    text = source()
    assert 'install -m 0400 "$gate" "$staged_gate"' in text
    assert 'install -m 0400 "$core" "$staged_core"' in text
    assert 'install -m 0400 "$clearance_validator" "$staged_validator"' in text
    assert 'install -m 0400 "$publisher" "$staged_publisher"' in text
    assert '"$python" "$staged_validator" --clearance-json "$clearance"' in text
    assert text.count("revalidate_execution_identity") >= 5
    assert 'require_hash "$staged_gate" "$expected_gate"' in text
    assert 'require_hash "$staged_core" "$expected_core"' in text


def test_literal_final_preexec_helper_rechecks_complete_identity() -> None:
    text = source()
    start = text.index("revalidate_execution_identity() {")
    end = text.index("\n}\n\nstop_active()", start)
    helper = text[start:end]
    required = (
        '"$(readlink -f -- "$0")" == "$runner_path"',
        '"$(canonical_self_hash)" == "$expected_self"',
        'git -C "$vllm" rev-parse HEAD',
        'git -C "$vllm" status --porcelain --untracked-files=no',
        'require_hash "$authority" "$expected_authority"',
        'readlink -f "$python"',
        '"$(digest "$python")" == "$expected_python"',
        'require_hash "$torch_root/__init__.py" "$expected_torch_init"',
        'require_hash "$torch_root/version.py" "$expected_torch_version_file"',
        "assert sys.version.split()[0] == expected_python",
        "assert torch.__version__ == expected_torch",
        "assert torch.version.git_version == expected_git",
        "assert str(torch.version.xpu) == expected_xpu",
        'require_hash "$gate" "$expected_gate"',
        'require_hash "$core" "$expected_core"',
        'require_hash "$clearance_validator" "$expected_clearance_validator"',
        'require_hash "$publisher" "$expected_publisher"',
        'require_hash "$staged_gate" "$expected_gate"',
        'require_hash "$staged_core" "$expected_core"',
        'require_hash "$staged_validator" "$expected_clearance_validator"',
        'require_hash "$staged_publisher" "$expected_publisher"',
        '"$(digest "$clearance")" == "$clearance_sha"',
        '"$(digest "${result}/clearance.json")" == "$clearance_sha"',
        '"$python" "$staged_validator" --clearance-json "$clearance"',
        "findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models",
        '[[ -z "$(active_runtime_processes)" ]]',
        '"$(current_nvme_aer)" == "$nvme_aer_baseline"',
        '"$(current_root_aer)" == "$root_aer_baseline"',
    )
    for contract in required:
        assert contract in helper, contract
    assert (
        "revalidate_execution_identity\n"
        "setsid timeout --signal=TERM --kill-after=30s 1200s env -i"
    ) in text


def test_evidence_is_transactional_no_clobber_and_checksummed() -> None:
    text = source()
    assert 'result="${result_final}.staging"' in text
    assert "gate-result.json.tmp" in text
    assert "gate.stderr.log.tmp" in text
    assert '"${result}/frozen/$(basename "$publisher")"' in text
    assert '--stage-dir "$result" --final-dir "$result_final"' in text


def test_validate_only_is_cpu_only_and_has_no_path_side_effect() -> None:
    assert not RESULT.exists() and not RESULT.is_symlink()
    assert not STAGE.exists() and not STAGE.is_symlink()
    assert not CACHE.exists() and not CACHE.is_symlink()
    environment = dict(os.environ)
    environment["Q38_HC_GATE_MIX_A1_VALIDATE_ONLY"] = "1"
    completed = subprocess.run(
        [str(RUNNER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "PASS: HC gate-mix exact-staged A1 static validation\n"
    assert not RESULT.exists() and not RESULT.is_symlink()
    assert not STAGE.exists() and not STAGE.is_symlink()
    assert not CACHE.exists() and not CACHE.is_symlink()


def test_runner_contains_no_reboot_or_full_model_launch() -> None:
    text = source()
    assert "reboot" not in text.lower()
    assert "systemctl" not in text
    assert "vllm serve" in text  # process rejection pattern only
    assert "model.safetensors" not in text
