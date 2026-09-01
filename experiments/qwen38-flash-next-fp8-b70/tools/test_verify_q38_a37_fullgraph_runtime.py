import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a37-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a37_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mode_none_allows_operator_cache(tmp_path) -> None:
    cache_file = tmp_path / "fxgraph" / "entry.py"
    cache_file.parent.mkdir()
    cache_file.write_text("operator helper\n", encoding="utf-8")
    log = (
        "<CompilationMode.NONE: 0>\n"
        "Inductor compilation was disabled by user settings\n"
    )
    MODULE.validate_compile_identity(log)
    assert MODULE.cache_manifest(tmp_path) == [
        {"path": "fxgraph/entry.py", "size_bytes": 16}
    ]


@pytest.mark.parametrize(
    "log",
    [
        "Inductor compilation was disabled by user settings\n",
        "<CompilationMode.NONE: 0>\n",
        (
            "<CompilationMode.NONE: 0>\n"
            "Inductor compilation was disabled by user settings\n"
            "Compiling a graph for compile range [1, 64] takes 2.0 s\n"
        ),
        (
            "<CompilationMode.NONE: 0>\n"
            "Inductor compilation was disabled by user settings\n"
            "torch.compile took 2.0 s in total\n"
        ),
    ],
)
def test_missing_or_contradictory_compile_receipt_is_rejected(log) -> None:
    with pytest.raises(MODULE.CORE.VerificationError):
        MODULE.validate_compile_identity(log)


def test_base_verifier_hash_mismatch_is_rejected(tmp_path) -> None:
    changed = tmp_path / "changed-verifier.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="base verifier hash changed"):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)


def write_trace(path, records) -> None:
    path.write_text(
        "\n".join("I0000 " + json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_trace_accepts_only_hash_bound_nested_helper(monkeypatch, tmp_path) -> None:
    target = next(iter(MODULE.ALLOWED_COMPILED_TARGETS))
    expected = MODULE.ALLOWED_COMPILED_TARGETS[target]
    monkeypatch.setattr(
        MODULE.CORE,
        "sha256",
        lambda path: expected if str(path.resolve()) == target[0] else "wrong",
    )
    write_trace(
        tmp_path / "dedicated_log_torch_trace_test.log",
        [
            {"str": [target[0], 7]},
            {
                "dynamo_start": {
                    "stack": [{"filename": 7, "name": target[1], "line": target[2]}]
                }
            },
        ],
    )
    events = MODULE.trace_compilations(tmp_path)
    assert len(events) == 1
    assert events[0]["source_sha256"] == expected


def test_trace_rejects_unknown_target(tmp_path) -> None:
    write_trace(
        tmp_path / "dedicated_log_torch_trace_test.log",
        [
            {"str": ["/tmp/qwen_root.py", 9]},
            {
                "dynamo_start": {
                    "stack": [{"filename": 9, "name": "forward", "line": 1}]
                }
            },
        ],
    )
    with pytest.raises(MODULE.CORE.VerificationError, match="unexpected compiled"):
        MODULE.trace_compilations(tmp_path)


def test_trace_rejects_missing_logs(tmp_path) -> None:
    with pytest.raises(MODULE.CORE.VerificationError, match="logs are absent"):
        MODULE.trace_compilations(tmp_path)


def test_trace_rejects_corrupt_top_level_record(tmp_path) -> None:
    trace = tmp_path / "dedicated_log_torch_trace_test.log"
    trace.write_text("truncated dynamo_start\n", encoding="utf-8")
    with pytest.raises(MODULE.CORE.VerificationError, match="unparseable"):
        MODULE.trace_compilations(tmp_path)
