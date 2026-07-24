"""CPU-only contract tests for the pair-counter authorization gate."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import gate_laguna_shared_gate_up_mm_counters as gate


SOURCE = Path(gate.__file__).resolve()


def test_protocol_is_exact_pair_aware_one_shot_counter_scope() -> None:
    protocol = gate.PROTOCOL
    assert protocol["card_order"] == [0, 1, 2, 3]
    assert protocol["card_execution"] == "sequential"
    assert protocol["arms"] == ["A1", "B1", "B2", "A2"]
    assert protocol["pairs_per_arm"] == 13
    assert protocol["selected_gemm_calls"] == 26
    assert protocol["discard_pair_indices"] == [0, 1]
    assert protocol["retained_pair_indices"] == list(range(2, 13))
    assert protocol["retained_gemm_samples"] == 22
    assert protocol["completion_bounded_before_and_after_each_pair"] is True
    assert protocol["eviction_bytes_before_each_pair"] == 128 * 1024 * 1024
    assert {
        "merged_N512",
        "logical_B16",
        "concatenation",
        "packing",
        "custom_fusion",
        "reorder",
        "overlap",
        "shared_down_MM",
    } == set(protocol["forbidden"])


def test_child_template_is_profiler_only_and_hash_bound() -> None:
    template = gate.child_command_template()
    assert template == gate.PROTOCOL["unitrace"]["argv_template"]
    assert template[:8] == [
        "/usr/bin/sudo",
        "-S",
        "-p",
        "",
        "-E",
        "--",
        "/usr/bin/env",
        "-i",
    ]
    assert "--device-timing" in template
    assert "--metric-query" in template
    assert template[template.index("--group") + 1] == "ComputeBasic"
    assert template[template.index("--include-kernels") + 1] == "gemm_kernel"
    assert {
        "{fixture_sha256}",
        "{authorization_sha256}",
        "{protocol_sha256}",
        "{fixture_output}",
    } <= set(template)
    assert all("api" not in item.lower() for item in template)


def test_action_boundary_never_authorizes_endpoint_model_network_or_reboot() -> None:
    proposed = gate.expected_actions(True)
    assert proposed["component_passed"] is True
    assert proposed["tooling_frozen"] is True
    assert proposed["counter_execution_authorized"] is True
    assert proposed["counter_execution_performed"] is False
    for name in (
        "counter_gate_evaluated",
        "endpoint_authorized",
        "service_authorized",
        "model_generation_authorized",
        "model_generation_performed",
        "network_authorized",
        "network_access_performed",
        "payload_authorized",
        "payload_created",
        "submission_authorized",
        "submission_performed",
        "reboot_authorized",
    ):
        assert proposed[name] is False
    assert all(value is False for value in gate.expected_actions(False).values())


def test_campaign_paths_freeze_all_16_arms_and_phase_seals() -> None:
    root = gate.RUNS / "shared-gate-up-m8-counters-20990101T000000Z"
    paths = gate.campaign_paths(root)
    assert paths["root"] == str(root)
    assert paths["preflight_failure"] == f"{root}-preflight-failure.json"
    assert paths["intent"] == str(root / "campaign.intent.json")
    assert paths["abandoned"] == str(root / "campaign.abandoned.json")
    assert paths["open"] == str(root / "campaign.open.json")
    assert paths["complete"] == str(root / "campaign.complete.json")
    assert paths["analysis"] == str(root / "analysis.json")
    assert paths["terminal"] == str(root / "campaign-terminal.json")
    assert paths["final_manifest"] == str(root / "counter-final-manifest.json")
    assert [(entry["rank"], entry["arm"]) for entry in paths["arms"]] == [
        (rank, arm) for rank in range(4) for arm in gate.ARMS
    ]
    assert all(
        entry["environment"]["ZE_AFFINITY_MASK"] == str(entry["rank"])
        and entry["environment"]["VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM"] == "1"
        and entry["environment"]["VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM"] == "0"
        for entry in paths["arms"]
    )


@pytest.mark.parametrize(
    "root",
    (
        Path("/tmp/shared-gate-up-m8-counters-20990101T000000Z"),
        gate.RUNS / "wrong-name",
        Path("shared-gate-up-m8-counters-20990101T000000Z"),
    ),
)
def test_campaign_path_rejects_noncanonical_roots(root: Path) -> None:
    with pytest.raises(RuntimeError, match="campaign root must"):
        gate.campaign_paths(root)


def test_mandatory_tool_map_includes_each_runtime_and_cpu_test() -> None:
    assert {
        "authorization_gate",
        "authorization_gate_tests",
        "fixture",
        "fixture_tests",
        "parser",
        "parser_tests",
        "runner",
        "runner_tests",
        "analyzer",
        "analyzer_tests",
        "component_contract",
        "component_runtime",
        "stage0_contract",
        "stage0_runtime",
    } == set(gate.MANDATORY_TOOLS)
    assert gate.sha(gate.CONTRACT_NOTE) == gate.EXPECTED["tooling_note_sha256"]


def test_gate_source_has_no_device_profiler_or_model_execution_path() -> None:
    source = SOURCE.read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "torch" not in imported
    assert source.count("xpu-smi") == 1  # frozen host-tool identity only
    assert "unitrace" not in {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "subprocess.Popen" not in source
