#!/home/steve/.venvs/vllm-xpu/bin/python3
"""Bind the historical GDN history gate to grouped full-serving stage A2.

The historical tool remains byte-unchanged.  This wrapper changes only its
execution-stage identities.  A24/A25 are still validated against their
original stage and original runtime-build commit.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path("/home/steve/llm-optimizations")
HISTORICAL_TOOL = (
    REPO / "experiments/qwen38-flash-next-fp8-b70/tools/"
    "check-q38-flash-next-gdn-history-replay.py"
)
SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_STAGE = Path("/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2")
CANDIDATE_MANIFEST = Path(
    "/mnt/fast-ai/qwen38-build/"
    "runtime-serving-hcgrouped-eeee7d6-a2-evidence/runtime-stage.sha256"
)
REFERENCE_STAGE = Path("/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70")
REFERENCE_RUNTIME_BUILD_COMMIT = "2f829747503c77d4814834dffd0840fb1dd9f75a"
CANDIDATE_RUNTIME_BUILD_COMMIT = "eeee7d671abfa964626baa18da2174bb92cac80a"
CANDIDATE_GDN_SOURCE_SHA256 = (
    "9ce22dec376dd58a3c4b5bab68a2bb35e96cf20bfbf5b51d1fd956b4cef029bd"
)
CANDIDATE_MANIFEST_SHA256 = (
    "a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d"
)
CANDIDATE_NATIVE_SHA256 = (
    "8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76"
)
CANDIDATE_GDN_SHA256 = (
    "6c9ba1f12838b3eaa27e91610f0344fbf11671bfee204c6a9a68564fc654c17e"
)


def load_historical():
    specification = importlib.util.spec_from_file_location(
        "q38_gdn_history_serving_a2_base", HISTORICAL_TOOL
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load historical GDN gate: {HISTORICAL_TOOL}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


MODULE = load_historical()
MODULE.SCRIPT_PATH = SCRIPT_PATH
MODULE.STAGE = CANDIDATE_STAGE
MODULE.STAGE_PACKAGE = CANDIDATE_STAGE / "vllm_xpu_kernels"
MODULE.STAGE_MANIFEST = CANDIDATE_MANIFEST
MODULE.EXPECTED = dict(MODULE.EXPECTED)
MODULE.EXPECTED.update(
    {
        "stage_manifest_sha256": CANDIDATE_MANIFEST_SHA256,
        "native_extension_sha256": CANDIDATE_NATIVE_SHA256,
        "gdn_library_sha256": CANDIDATE_GDN_SHA256,
        "runtime_build_commit": CANDIDATE_RUNTIME_BUILD_COMMIT,
        "gdn_source_sha256": CANDIDATE_GDN_SOURCE_SHA256,
    }
)


def validate_historical_reference_identities():
    execution_stage = MODULE.STAGE
    execution_commit = MODULE.EXPECTED["runtime_build_commit"]
    try:
        MODULE.STAGE = REFERENCE_STAGE
        MODULE.EXPECTED["runtime_build_commit"] = REFERENCE_RUNTIME_BUILD_COMMIT
        return MODULE.validate_reference_identities_original()
    finally:
        MODULE.STAGE = execution_stage
        MODULE.EXPECTED["runtime_build_commit"] = execution_commit


MODULE.validate_reference_identities_original = MODULE.validate_reference_identities
MODULE.validate_reference_identities = validate_historical_reference_identities


if __name__ == "__main__":
    raise SystemExit(MODULE.main())
