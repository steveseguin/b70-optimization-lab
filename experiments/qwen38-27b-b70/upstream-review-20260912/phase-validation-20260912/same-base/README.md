# Same-base current-main confirmation

**Current main stock: 14 passed / 8 failed. Same main plus exact PR #51565 delta:
22 passed.** Both arms use identical current-main helpers and identical fixtures.

Source main: `d8f840071efd631f71b06d4b31cb6dba2275a356`.
PR head rechecked unchanged: `53995de1e5781416206cabfc3ddf539611f82cc0`.

The exact GitHub PR file diff (`../pr51565-gdn.patch`) applied to the isolated
current-main builder snapshot using `patch --batch --fuzz=0 -p1` with no offsets,
fuzz, rejected hunks, or manual conflict resolution. `applied.patch` records the
resulting complete source delta. `identity.json` records source SHA256 values.
The utils and FLA index helpers were freshly downloaded from the pinned main.

Both arms execute all actual builder methods with the same CPU dependency
adapters described in the parent README, not a complete installed runtime.
This removes the prior old-PR-head versus current-main confound for these CPU
metadata cases; it does not remove the adapters or qualify GPU kernels/graphs.

Replay from repo root:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m pytest -p no:cacheprovider -q experiments/qwen38-27b-b70/upstream-review-20260912/phase-validation-20260912/same-base/test_full_builder.py
GDN_ARM=stock /home/steve/.venvs/vllm-xpu/bin/python -m pytest -p no:cacheprovider -q experiments/qwen38-27b-b70/upstream-review-20260912/phase-validation-20260912/same-base/test_full_builder.py
```

Logs: `candidate.log`, `stock.log`. Upstream integration/device gates remain as
recorded in the parent packet. No GPU or shared runtime source modifications.
