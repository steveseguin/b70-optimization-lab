import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "analyze-muse-dflash-repair-forest.py"
SPEC = importlib.util.spec_from_file_location("analyze_muse_repair_forest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(token, prob, rank=0):
    return {"rank": rank, "token": token, "prob": prob}


def positions():
    return [
        [candidate(10, 0.6), candidate(11, 0.4, 1)],
        [candidate(20, 0.8), candidate(21, 0.2, 1)],
        [candidate(30, 0.9), candidate(31, 0.1, 1)],
    ]


def test_full_spine_is_preserved_before_repairs():
    tree = MODULE.build_repair_forest(positions(), 3, 1, 0, "depth")
    node = tree[0][10]
    node = tree[node][20]
    assert 30 in tree[node]
    assert 11 not in tree[0]


def test_repair_branch_can_carry_stale_suffix():
    record = {"anchor": 0, "drafted": 3, "candidates": positions()}
    targets = {0: 11, 1: 20, 2: 30}
    assert MODULE.repair_match_length(record, targets, 5, 1, 1, "depth") == 2
    assert MODULE.repair_match_length(record, targets, 6, 1, 2, "depth") == 3


def test_odds_order_spends_single_repair_on_uncertain_position():
    tree = MODULE.build_repair_forest(positions(), 4, 1, 0, "odds")
    # Position zero has the largest alternative/top-1 odds (0.4/0.6).
    assert 11 in tree[0]
    main0 = tree[0][10]
    assert 21 not in tree[main0]
