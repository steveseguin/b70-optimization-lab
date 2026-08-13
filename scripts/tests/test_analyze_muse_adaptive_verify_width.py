import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "analyze-muse-adaptive-verify-width.py"
SPEC = importlib.util.spec_from_file_location("analyze_muse_adaptive_width", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(token):
    return {"rank": 0, "token": token, "prob": 1.0}


def test_interpolates_unmeasured_width():
    assert MODULE.interpolate_cost({1: 10.0, 3: 14.0}, 2) == 12.0


def test_oracle_chooses_only_useful_width_when_extra_rows_cost_more():
    request = {
        "targets": {0: 10, 1: 20, 2: 99},
        "records": [{
            "anchor": 0,
            "drafted": 2,
            "candidates": [[candidate(10)], [candidate(21)]],
        }],
    }
    result = MODULE.oracle_adaptive_width(
        request, {1: 10.0, 2: 11.0, 3: 30.0}, fixed_ms=0.0, max_draft=2
    )
    assert result["rounds"] == 2
    assert result["accepted_tokens"] == 1
    assert result["width_histogram"] == {"0": 1, "1": 1}
