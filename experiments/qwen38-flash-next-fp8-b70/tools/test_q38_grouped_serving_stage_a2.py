#!/home/steve/.venvs/vllm-xpu/bin/python3
"""CPU-only contract tests for grouped full-serving stage A2 tooling."""

from __future__ import annotations

import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parent


def load(name: str, filename: str):
    path = TOOLS / filename
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSPECTOR = load(
    "q38_grouped_stage_a2_inspector",
    "inspect-q38-grouped-serving-stage-a2.py",
)
GDN = load(
    "q38_grouped_stage_a2_gdn",
    "check-q38-flash-next-gdn-history-serving-a2.py",
)
TEST_RUNNER = load(
    "q38_grouped_stage_a2_test_runner",
    "run-q38-grouped-serving-stage-tests-a2.py",
)
QUALIFIER = (TOOLS / "qualify-q38-grouped-serving-stage-a2.sh").read_text()


def test_inspector_requires_both_native_operations() -> None:
    assert INSPECTOR.REQUIRED_OPERATORS == {
        "_xpu_C::cutlass_grouped_gemm_interface",
        "_xpu_C::gdn_attention",
    }
    assert len(INSPECTOR.EXPECTED_GDN_ARGUMENTS) == 23
    assert INSPECTOR.EXPECTED_GDN_ARGUMENTS[0] == "core_attn_out"
    assert INSPECTOR.EXPECTED_GDN_ARGUMENTS[-1] == "reorder_input"


def test_gdn_execution_and_reference_identities_are_separate() -> None:
    observed = {}
    original = GDN.MODULE.validate_reference_identities_original
    try:
        GDN.MODULE.validate_reference_identities_original = lambda: observed.update(
            {
                "stage": GDN.MODULE.STAGE,
                "commit": GDN.MODULE.EXPECTED["runtime_build_commit"],
            }
        )
        GDN.validate_historical_reference_identities()
    finally:
        GDN.MODULE.validate_reference_identities_original = original
    assert observed == {
        "stage": GDN.REFERENCE_STAGE,
        "commit": GDN.REFERENCE_RUNTIME_BUILD_COMMIT,
    }
    assert GDN.MODULE.STAGE == GDN.CANDIDATE_STAGE
    assert (
        GDN.MODULE.EXPECTED["runtime_build_commit"]
        == GDN.CANDIDATE_RUNTIME_BUILD_COMMIT
    )


def test_focused_suite_counts_are_frozen() -> None:
    assert TEST_RUNNER.SUITES["hc"][1] == 5
    assert TEST_RUNNER.SUITES["config"][1] == 25


def test_candidate_manifest_stays_external_to_package() -> None:
    candidate = INSPECTOR.STAGES["candidate"]
    assert candidate["package"] == GDN.CANDIDATE_STAGE / "vllm_xpu_kernels"
    assert candidate["manifest"] == GDN.CANDIDATE_MANIFEST
    assert candidate["manifest"].parent.name.endswith("-evidence")
    assert candidate["manifest"].parent != candidate["package"]


def test_qualifier_closes_finalizer_loader_and_gdn_contracts() -> None:
    assert "finalizer-evidence.sha256" in QUALIFIER
    for library in (
        "_xpu_C.abi3.so",
        "libgdn_attn_kernels_xe_2.so",
        "libgrouped_gemm_xe_2.so",
    ):
        assert library in QUALIFIER
    assert "Library runpath: [$ORIGIN]" in QUALIFIER
    assert '.status == "pass" and .valid == true and .result_count == 2' in QUALIFIER
    assert "refuse_render_owners\nverify_static_identity" in QUALIFIER
    assert '[[ "$journal_rc" == 0 ]]' in QUALIFIER
