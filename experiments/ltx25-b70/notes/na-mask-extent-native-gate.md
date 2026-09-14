# Native gate prepared; current fault correctly refuses it

The inactive [mask extent patch](na-mask-extent-01.md) now has a separate
`scripts/test-na-mask-extent-native.py` qualification helper. It extracts the
four exact functions from each saved, hash-checked source copy, preserving both
production tile budgets and all original arithmetic. It does not modify an
installed module or load model weights.

The future native screen requires an explicit `--device cpu` or `--device xpu:3`
and a new `--output` receipt path. Ten small mask comparisons and six small
attention comparisons cover BF16/F32, singleton/boundary/oversized windows,
causal and mixed axes, and both explicit/default scales. Each compares original,
candidate and repeated candidate bytes, layout and finiteness with strict
deterministic algorithms enabled. These tiny cases do not exercise production
tiling, actual decoder weights, full-clip parity, continuation or timing.
The orchestrator owns device availability and exclusive GPU scheduling.

The only executed invocation was standard-library check-only:

```text
python3 -B -S experiments/ltx25-b70/scripts/test-na-mask-extent-native.py --device cpu --check-only --output experiments/ltx25-b70/data/na-mask-extent-01/native-check-only-fault.json
```

It correctly returned exit2, `halted-fault-before-torch-import`, no cases and
`torch_imported=false`. This is evidence for the fault guard, not a native
qualification pass. The same fault is checked between native calls/copies and
before success. No fallback, restart or retry is implemented.

A separate stdlib source review extracted/compiled both AST modules without
executing their tensor functions, verified unchanged constants, and checked
the fault receipt against the current script hash. Evidence:
`data/na-mask-extent-01/native-gate-source-review.json`.
The patch itself applied cleanly to a temporary original source copy and
produced byte-for-byte the stored candidate; installed source still equals
the original (`patch-application-check.json`). No native import or server
action was performed during either review.
