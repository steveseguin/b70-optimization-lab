# Gate/up oneDNN batch=2 confirmation on current retained stack

Date: 2026-08-13

Decision: **retain in the experimental century stack**. The existing
default-off gate/up batch=2 path is exact and saves about `0.190 ms/round` on
the current top15/heap/allreduce-last-event stack. This confirmation is more
relevant than the earlier +0.34% screen because it uses the current final
kernel/runtime identity and reversed controls.

Source implementation is already present in
`/home/steve/src/llama.cpp-muse-100`; runtime gate:
`GGML_SYCL_DNNL_FFN_BATCH2=1`. The candidate log proves the real first hit:

`blk.0.ffn_gate.weight`, local `m=4992 n=2 k=6656`, weight stride 66,453,504
bytes, output stride 39,936 elements.

Config:
`experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ffn-batch2-current-full-cac.json`

Raw JSONL:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ffn-batch2-current-full-cac-20260813.jsonl`

SHA-256:
`0e826abe4eb52d9ebad63f3aa227cc7aa5176b6ef9010ef9ee56a89aedf80a1e`.

## Full 256-token C/A/C

| Arm | Prose | Code | JSON | Arithmetic mean |
|---|---:|---:|---:|---:|
| control before | 57.515 | 83.134 | 101.432 | 80.694 |
| batch2 | 57.750 | 83.388 | 101.499 | 80.879 |
| control after | 57.309 | 83.127 | 101.178 | 80.538 |

All arms emitted canonical hashes and accepted 172 / 197 / 207. Prose drafted
count varied by one in the candidate (1198 versus 1199), without changing
accepted count or emitted text.

Drift-interpolated round savings:

- prose: `0.310858 ms`;
- code: `0.161176 ms`;
- JSON: `0.098653 ms`;
- unweighted mean: `0.190229 ms`.

## Updated budget-15 DDTree arithmetic

Applying the class-specific batch2 savings and measured unified-KV overhead to
the prior zero-bookkeeping DDTree model gives:

- prose: `75.650 tok/s`;
- code: `103.569 tok/s`;
- JSON: `120.610 tok/s`;
- arithmetic mean: **`99.943 tok/s`**.

Only `0.029 ms/round` of further uniform saving is required mathematically,
but every positive DDTree bookkeeping or multi-sequence mask cost adds directly
to that requirement. This is not an honest >100 result yet. It makes the
16-row branch-layout timing/correctness probe the next decisive step.
