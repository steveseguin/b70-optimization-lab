"""CPU-only source-contract tests for the gate+up counter fixture."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path(__file__).with_name("profile_laguna_shared_gate_up_mm_counter_fixture.py")
TREE = ast.parse(SOURCE.read_text())


def function(name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and (
            isinstance(child.func, ast.Name)
            and child.func.id == name
            or isinstance(child.func, ast.Attribute)
            and child.func.attr == name
        )
    ]


def string_constants(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def test_selected_scope_is_one_ordered_pair_call_per_loop() -> None:
    main = function("main")
    loops = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "range"
        and isinstance(node.iter.args[0], ast.Name)
        and node.iter.args[0].id == "PAIRS"
    ]
    assert len(loops) == 1
    assert len(calls(loops[0], "_selected_pair")) == 1
    assert len(calls(main, "_selected_pair")) == 1
    assert not calls(main, "_control_pair")
    assert not calls(main, "_candidate_pair")


def test_control_and_candidate_each_keep_gate_then_up_as_two_calls() -> None:
    control = function("_control_pair")
    candidate = function("_candidate_pair")
    control_calls = calls(control, "_control")
    candidate_calls = calls(candidate, "_candidate")
    assert len(control_calls) == len(candidate_calls) == 2
    assert [
        call.args[1].id for call in control_calls if isinstance(call.args[1], ast.Name)
    ] == ["gate_expanded", "up_expanded"]
    assert [
        call.args[1].func.value.id
        for call in candidate_calls
        if isinstance(call.args[1], ast.Call)
        and isinstance(call.args[1].func, ast.Attribute)
        and isinstance(call.args[1].func.value, ast.Name)
    ] == ["gate_weight", "up_weight"]


def test_fixture_requires_authorization_protocol_and_source_hashes() -> None:
    strings = string_constants(function("main"))
    assert {
        "--expected-fixture-sha256",
        "--authorization-sha256",
        "--protocol-sha256",
        "authorization_sha256",
        "protocol_sha256",
        "fixture_source_sha256",
        "input_fixture_sha256",
        "all_pair_output_sha256",
    } <= strings


def test_environment_is_exact_component_contract_environment() -> None:
    environment = function("_require_pair_environment")
    attributes = [
        node
        for node in ast.walk(environment)
        if isinstance(node, ast.Attribute) and node.attr == "environment"
    ]
    assert len(attributes) == 1
    strings = string_constants(environment)
    assert {
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM",
    } <= strings


def test_writer_is_exclusive_and_durable_without_subprocesses() -> None:
    source = SOURCE.read_text()
    writer = function("exclusive_json")
    attributes = {
        node.attr for node in ast.walk(writer) if isinstance(node, ast.Attribute)
    }
    assert {"O_EXCL", "O_NOFOLLOW", "O_DIRECTORY"} <= attributes
    assert len(calls(writer, "fsync")) == 2
    assert "import subprocess" not in source
    assert "subprocess." not in source
