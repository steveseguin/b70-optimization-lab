import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "analyze-muse-ddtree-prefix-trace.py"
SPEC = importlib.util.spec_from_file_location("analyze_muse_ddtree", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(token, prob, rank=0):
    return {"rank": rank, "token": token, "prob": prob}


def test_best_first_tree_adds_high_value_alternative():
    positions = [
        [candidate(10, 0.6), candidate(11, 0.4, 1)],
        [candidate(20, 0.9), candidate(21, 0.1, 1)],
    ]

    # Budget 2 is the top-1 chain.  The third node is the more valuable
    # first-position sibling, matching the official best-first ordering.
    tree2 = MODULE.build_child_maps(positions, 2)
    tree3 = MODULE.build_child_maps(positions, 3)
    assert 11 not in tree2[0]
    assert 11 in tree3[0]
    assert 20 in tree2[tree2[0][10]]


def test_trace_simulation_reproduces_linear_and_tree_walk():
    request = {
        "targets": {0: 1, 1: 11, 2: 20, 3: 30},
        "records": [
            {
                "anchor": 1,
                "drafted": 2,
                "candidates": [
                    [candidate(10, 0.6), candidate(11, 0.4, 1)],
                    [candidate(20, 0.9), candidate(21, 0.1, 1)],
                ],
            },
            {
                "anchor": 2,
                "drafted": 2,
                "candidates": [
                    [candidate(20, 0.9), candidate(22, 0.1, 1)],
                    [candidate(30, 0.9), candidate(31, 0.1, 1)],
                ],
            },
        ],
    }
    linear = MODULE.simulate(
        request,
        lambda record, targets: 0 if record is None else MODULE.linear_match_length(record, targets, 0.0),
    )
    tree = MODULE.simulate(
        request,
        lambda record, targets: 0 if record is None else MODULE.tree_match_length(record, targets, 4),
    )
    assert linear == {
        "rounds": 3,
        "accepted_tokens": 2,
        "emitted_tokens": 4,
        "emitted_per_round": 4 / 3,
    }
    assert tree == {
        "rounds": 2,
        "accepted_tokens": 2,
        "emitted_tokens": 4,
        "emitted_per_round": 2.0,
    }
