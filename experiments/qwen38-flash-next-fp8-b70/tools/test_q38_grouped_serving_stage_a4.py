#!/home/steve/.venvs/vllm-xpu/bin/python3
"""CPU-only contract tests for the additive A4 schema inspector."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


INSPECTOR_PATH = Path(__file__).with_name("inspect-q38-grouped-serving-stage-a4.py")
SPEC = importlib.util.spec_from_file_location(
    "q38_grouped_stage_a4_inspector", INSPECTOR_PATH
)
assert SPEC is not None and SPEC.loader is not None
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)


def write_payload(path: Path, schemas: set[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "passed",
                "schemas": sorted(schemas),
                "gdn_argument_names": list(INSPECTOR.BASE.EXPECTED_GDN_ARGUMENTS),
            }
        ),
        encoding="utf-8",
    )


def test_expected_additive_set_is_exact_and_contains_grouped() -> None:
    assert len(INSPECTOR.EXPECTED_ADDED_SCHEMAS) == 14
    assert (
        sum(
            schema.startswith(f"{INSPECTOR.GROUPED_OPERATOR}(")
            for schema in INSPECTOR.EXPECTED_ADDED_SCHEMAS
        )
        == 1
    )


def test_compare_accepts_preserved_base_plus_exact_additions(tmp_path: Path) -> None:
    accepted = tmp_path / "accepted.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "output.json"
    write_payload(accepted, {"_xpu_C::old() -> ()"})
    write_payload(
        candidate,
        {"_xpu_C::old() -> ()"} | INSPECTOR.EXPECTED_ADDED_SCHEMAS,
    )
    INSPECTOR.compare(accepted, candidate, output)
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "passed"
    assert receipt["exact_expected_additive_set"] is True
    assert receipt["removed_schemas"] == []


@pytest.mark.parametrize("failure", ["removed", "extra"])
def test_compare_rejects_removed_or_unexpected_schema(
    tmp_path: Path, failure: str
) -> None:
    accepted = tmp_path / "accepted.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "output.json"
    base = {"_xpu_C::old() -> ()"}
    write_payload(accepted, base)
    schemas = set(INSPECTOR.EXPECTED_ADDED_SCHEMAS)
    if failure == "removed":
        pass
    else:
        schemas |= base | {"_xpu_C::unexpected() -> ()"}
    write_payload(candidate, schemas)
    with pytest.raises(INSPECTOR.BASE.ContractError):
        INSPECTOR.compare(accepted, candidate, output)
