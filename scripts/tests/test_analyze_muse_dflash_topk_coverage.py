import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "analyze-muse-dflash-topk-coverage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dflash_topk", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_first_mismatch_rank_and_full_accept():
    module = load_module()
    lines = [
        "draft candidate   0, pos   0:    101 (0.700)",
        "draft candidate   1, pos   0:    102 (0.200)",
        "draft candidate   2, pos   0:    103 (0.100)",
        "draft candidate   0, pos   1:    201 (0.600)",
        "draft candidate   1, pos   1:    202 (0.300)",
        "draft candidate   2, pos   1:    203 (0.100)",
        "accepted  1/ 2 draft tokens",
        "add accepted tokens: sampled=202, ids.size=2, n_draft=2",
        "stop processing: n_tokens = 20",
        "draft candidate   0, pos   0:    301 (0.900)",
        "draft candidate   1, pos   0:    302 (0.080)",
        "draft candidate   2, pos   0:    303 (0.020)",
        "accepted  1/ 1 draft tokens",
        "add accepted tokens: sampled=999, ids.size=2, n_draft=1",
        "stop processing: n_tokens = 22",
    ]
    result = module.parse_trace(lines)
    assert result["overall"]["rounds"] == 2
    assert result["overall"]["full_accept_rounds"] == 1
    assert result["overall"]["mismatch_rounds"] == 1
    assert result["overall"]["target_rank_histogram"] == {"2": 1}
    assert result["overall"]["top2_coverage"]["fraction_of_mismatches"] == 1.0
    assert len(result["requests"]) == 2


def test_rejects_incomplete_round():
    module = load_module()
    try:
        module.parse_trace(["draft candidate 0, pos 0: 101 (0.7)"])
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("expected incomplete trace to be rejected")
