import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "analyze-muse-dual-proposer-prefix-trace.py"
SPEC = importlib.util.spec_from_file_location("dual_trace", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def trace_lines(proposals, targets):
    lines = ["proposal trace target anchor=0 sampled=10"]
    emitted_targets = {0}
    for anchor, tokens in proposals.items():
        for pos, token in enumerate(tokens):
            lines.append(f"draft candidate   0, pos {pos:3d}: {token:6d} (   0.900)")
        lines.append(f"proposal trace anchor={anchor} drafted={len(tokens)}")
        lines.append(f"proposal trace target anchor={anchor} sampled={targets[anchor]}")
        emitted_targets.add(anchor)
    for anchor in sorted(set(targets) - emitted_targets):
        lines.append(f"proposal trace target anchor={anchor} sampled={targets[anchor]}")
    lines.append("stop processing: n_tokens = 4")
    return lines


def test_parse_and_ensemble_uses_complementary_longer_path():
    targets = {0: 10, 1: 11, 2: 12, 3: 13}
    dflash = MODULE.parse_trace(trace_lines({1: [11, 99], 2: [12, 13]}, targets))[0]
    dspark = MODULE.parse_trace(trace_lines({1: [11, 12], 2: [98, 13]}, targets))[0]

    result = MODULE.analyze_request(dflash, dspark, "test", 10.0)

    assert result["strategies"]["dflash_p000"]["rounds"] == 3
    assert result["strategies"]["dspark_p000"]["rounds"] == 2
    assert result["strategies"]["ensemble_dflash_p000"]["rounds"] == 2
    assert result["strategies"]["ensemble_dflash_p000"]["accepted_tokens"] == 2


def test_dflash_probability_cutoff_changes_simulated_length():
    lines = [
        "proposal trace target anchor=0 sampled=10",
        "draft candidate 0, pos 0: 11 (0.900)",
        "draft candidate 0, pos 1: 12 (0.100)",
        "proposal trace anchor=1 drafted=2",
        "proposal trace target anchor=1 sampled=11",
        "proposal trace target anchor=2 sampled=12",
        "stop processing: n_tokens = 3",
    ]
    request = MODULE.parse_trace(lines)[0]
    row = request["records"][0]

    assert MODULE.primary_tokens(row, 0.15) == [11]
    assert MODULE.primary_tokens(row, 0.0) == [11, 12]
