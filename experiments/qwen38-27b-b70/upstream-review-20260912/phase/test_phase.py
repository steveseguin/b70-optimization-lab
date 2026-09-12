#!/usr/bin/env python3
"""CPU regression of pinned actual helper/call, not GPU or full-builder execution."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import torch

ROOT = Path(__file__).resolve().parent
helper = next(
    n
    for n in ast.parse((ROOT / "source/utils.py").read_text()).body
    if isinstance(n, ast.FunctionDef) and n.name == "split_decodes_and_prefills"
)
ns = {"torch": torch, "CommonAttentionMetadata": object}
exec(compile(ast.Module(body=[helper], type_ignores=[]), "pinned-utils.py", "exec"), ns)
cases = [
    # name, lengths, phases, candidate-routing expectation (not all differences are defects)
    ("fresh-one", [1], [True], (0, 1, 0, 1)),
    ("fresh-two", [2], [True], (0, 1, 0, 2)),
    ("decode-one", [1], [False], (1, 0, 1, 0)),
    ("decode-many", [1, 1, 1], [False] * 3, (3, 0, 3, 0)),
    ("chunk-final-one", [1], [True], (0, 1, 0, 1)),
    ("chunk-long", [3], [True], (0, 1, 0, 3)),
    ("decode-fresh", [1, 1], [False, True], (1, 1, 1, 1)),
    ("decode-short-long-fresh", [1, 1, 3, 1], [False, True, True, True], (1, 3, 1, 5)),
    ("fresh-many", [1, 1], [True, True], (0, 2, 0, 2)),
    ("capture-padding", [1, 0], [False, False], (2, 0, 1, 0)),
    ("metadata-less-draft", [1], None, (1, 0, 1, 0)),
    ("metadata-less-capture", [1, 0], None, (2, 0, 1, 0)),
]
results = {}
for arm, filename in [("stock", "gdn_attn.py"), ("fixed", "gdn_attn.fixed.py")]:
    tree = ast.parse((ROOT / "source" / filename).read_text())
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "split_decodes_and_prefills"
    ]
    assert len(calls) == 1
    code = compile(ast.Expression(calls[0]), filename, "eval")
    rows = []
    for name, lengths, phases, expected in cases:
        m = SimpleNamespace(
            max_query_len=max(lengths),
            num_reqs=len(lengths),
            num_actual_tokens=sum(lengths),
            query_start_loc_cpu=torch.tensor([0] + lengths).cumsum(0),
            is_prefilling=None if phases is None else torch.tensor(phases),
        )
        observed = eval(code, dict(ns, m=m))
        rows.append(
            dict(
                name=name,
                observed=observed,
                expected=expected,
                passed=observed == expected,
            )
        )
    results[arm] = rows
stock_failures = [r["name"] for r in results["stock"] if not r["passed"]]
assert stock_failures == [
    "fresh-one",
    "chunk-final-one",
    "decode-fresh",
    "decode-short-long-fresh",
    "fresh-many",
]
assert all(r["passed"] for r in results["fixed"])
# A real regression gap in this local patch: trailing graph padding becomes
# prefill because the helper returns the entire suffix. PR #51565 handles this.
m = SimpleNamespace(
    max_query_len=1,
    num_reqs=3,
    num_actual_tokens=3,
    query_start_loc_cpu=torch.tensor([0, 1, 2, 2]),
    is_prefilling=torch.tensor([False, True, False]),
)
observed = eval(code, dict(ns, m=m))  # fixed call from the final arm
assert observed == (1, 2, 1, 2)
results["known_patch_gap"] = dict(
    case="decode-fresh-zero-query-padding",
    observed=observed,
    required_actual_partition=(1, 1, 1, 1),
    note="local patch counts padded row/token as prefill; PR #51565 excludes it",
)
results["scope"] = (
    "CPU tensors, AST-extracted unmodified helper and real GDN call; no GPU/full builder/numerics"
)
results["torch"] = torch.__version__
print(json.dumps(results, indent=2))
