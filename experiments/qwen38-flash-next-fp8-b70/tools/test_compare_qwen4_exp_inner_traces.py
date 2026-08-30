import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).with_name("compare-qwen4-exp-inner-traces.py")
SPEC = importlib.util.spec_from_file_location("compare_q38_traces", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_trace(
    path: Path, digest: str = "a" * 64, *, label: str = "model_input"
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rank": 0,
                "min_position_gate": 4000,
                "position_min": 4000,
                "position_max": 4000,
                "records": [
                    {
                        "label": label,
                        "tensors": {
                            "hidden_states": {
                                "dtype": "torch.bfloat16",
                                "shape": [1, 2],
                                "numel": 2,
                                "sha256": digest,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_identical(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    write_trace(left)
    write_trace(right)
    result = MODULE.compare(left, right)
    assert result["status"] == "identical"
    assert result["matching_tensor_prefix"] == 1


def test_first_digest_mismatch(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    write_trace(left)
    write_trace(right, "b" * 64)
    result = MODULE.compare(left, right)
    assert result["status"] == "digest_mismatch"
    assert result["matching_tensor_prefix"] == 0
    assert result["first_mismatch"]["label"] == "model_input"


def test_schema_mismatch_precedes_digest(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    write_trace(left)
    write_trace(right, "b" * 64, label="layer_0_output")
    result = MODULE.compare(left, right)
    assert result["status"] == "schema_mismatch"
    assert "label" in result["first_mismatch"]["schema"]
