# 2026-07-10: DDTree verifier row cost and native GDN contract

## Status and validity

This is an implementation/cost gate for the Qwen3.6 27B DDTree lane. It is
not an endpoint throughput result, not a target-quality result, and not
eligible for LocalMaxxing. The strict fresh headline remains `68.236263 tok/s`.

The prior offline oracle established a stable training-free acceptance gain:

- `k15 / budget15`: about `3.9355` visible tokens per target step with 16
  verifier rows;
- `k15 / budget30`: about `4.1982` visible tokens per target step with 31
  verifier rows;
- `k8 / budget32`: about `4.0156` visible tokens per target step with 33
  verifier rows.

The work here answers two next questions: how W4 target-body cost scales at
those row counts, and whether the existing production XPU GDN primitive can
represent a tree exactly rather than flattening siblings into a chain.

## Corrected W4A16 row-cost method

`scripts/bench-qwen27-w4a16-row-scaling.py` measures all six AutoRound/INC
projection shapes and weights them by the actual 48 GDN plus 16 full-attention
layer call counts. The first smoke synchronized after every individual call
and projected an impossible `~94 ms` W4 step. That was a harness error: it
charged host/device synchronization 256 times. The corrected harness records
16 operator calls between one pair of XPU timing events and reports device
event and wall time separately. The row-4 projection is now `~22.52 ms`, which
is consistent with prior target-body timing rather than contradicting it.

Four independent B70 runs used 20 warmups, 100 measured samples, and 16 calls
per sample:

| rows | mean projected W4 ms | mean delta vs rows4 | four-card delta range |
| ---: | ---: | ---: | ---: |
| 4 | 22.5220 | 0.0000 | 0.0000 |
| 9 | 25.9487 | +3.4267 | +3.2846 to +3.6094 |
| 16 | 26.7242 | **+4.2022** | **+4.0440 to +4.4558** |
| 17 | 28.8342 | +6.3122 | +6.1083 to +6.6014 |
| 31 | 31.5289 | **+9.0069** | **+8.7563 to +9.3045** |
| 33 | 38.7834 | **+16.2614** | **+16.1371 to +16.5026** |

The card-to-card spread is small. Row 33 crosses a consistently bad W4 kernel
boundary and should not be the first endpoint shape. Row 16 is the best first
prototype; row 31 remains a secondary acceptance/cost point.

Raw reports:

- `data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-w4a16-row-scaling-20260710.json`;
- the matching `gpu1`, `gpu2`, and `gpu3` reports in the same directory.

These values are a device-kernel cost model, not end-to-end timings. Applying
only the row delta to the current `~40.26 ms` MTP3 step projects roughly
`44.46 ms` at row 16, which would be only about `88.5 tok/s` at `3.9355`
visible tokens/step. Therefore DDTree acceptance alone does not prove 100
tok/s. The integrated path must also remove eager DFlash/tree overhead and
keep GDN plus verification graph-safe; a compact LM-head/top-k producer may
again matter at 16+ rows even though prior row-1..4 top-1 kernels were no-win.

## Exact tree-state contract

`scripts/check-gdn-tree-recurrent-exact.py` now defines and tests the state
transaction explicitly:

- nodes are topologically ordered and carry `parent_indices`;
- the root reads the pre-tree conv and SSM state;
- node `i` publishes its post-token conv and SSM state to a unique row;
- siblings read the same parent row and never each other's state;
- after target verification, the winning node's state row is copied exactly
  into the commit row;
- a deliberately flattened topological sequence must diverge for every
  non-chain tree.

The high-level PyTorch branch executor matches an independent root-to-node
replay. More importantly, `--native-indexed` exercises the already-built
`torch.ops._xpu_C.gdn_attention_indexed_decode` primitive once per tree depth.
Each destination row is unique and each source row is the logical parent's
published row, so nodes within a depth are race-free. Native bit parity is
checked against the same production one-token kernel replayed independently
for every root-to-node path; this avoids falsely requiring PyTorch reduction
order to equal the subgroup kernel's BF16 rounding order.

At the real Qwen27 local shape (`num_k_heads=16`, `num_v_heads=48`,
`head_k_dim=head_v_dim=128`), BF16 native outputs, conv states, SSM states,
`z` passthrough, and winning-path commits were bit-identical for:

- a 9-node chain;
- 9 root siblings;
- a 15-node binary tree;
- a 33-node wide/deep DDTree-like topology.

The flattened negative control diverged as required. The descriptive PyTorch
math oracle differs from the native kernel by at most normal publication-order
rounding (`<=0.001953125` in SSM state); it is not used to define native bit
parity. Full result:
`data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-gdn-tree-native-fullshape-20260710.json`.

## Implementation decision

Advance the 16-row lane in two stages:

1. use the existing parent-source indexed conv/GDN kernels in depth batches to
   establish an integrated correctness and cost upper bound;
2. replace the depth launches with one graph-static tree op if launch/state-row
   overhead is material. The single-launch design should leave persistent
   state read-only, write per-node state into reusable scratch, and promote
   only the target-verified winning path, matching Hipfire's proven GDN-tape
   transaction without porting HIP code blindly.

No endpoint claim, quality promotion, or LocalMaxxing submission is allowed
until the fixed realistic cold suite, `cached_tokens=0`, repeat64 quality,
same-window/card crossover, and full identity/log gates pass.

## Implemented graph-static whole-tree op

The row-16 follow-up is now implemented in the XPU extension as
`torch.ops._xpu_C.gdn_attention_tree_indexed_decode`. The public call accepts
one topologically ordered token/state/source table. Its two underlying kernels
(causal conv and GDN recurrence) each loop through all rows inside one launch,
so a parent publication is consumed by its children in program order without
making persistent state writable. The established indexed op remains intact
and is still the independent depth-batched comparison path.

The implementation built successfully for `pvc`, `bmg`, `bmg-g21-a0`, and
`bmg-g31-a0` from XPU-kernels source commit
`3b4effeeffd83f6ef4696bbe7e76d924a0e9d171`. The installed diagnostic binary
SHA-256 is
`825173365a9b05fd78f56860a4823f9d9418b85fec08f43afd4244c4acdc558f`.
Because that source checkout already contains related uncommitted ReplaySSM
work, the exact four-file build state is preserved as a deliberately composite
patch rather than mislabeled as a clean upstream delta:

- `patches/qwen27-dflash-gdn-tree-loop-xpu-build-state-20260710.patch`;
- patch SHA-256
  `1861bf486e758909b6cac546bab5b4b34320730312965deb737c559a080f05d5`.

At the real Qwen27 BF16 GDN shape, every four-card row-16 and row-33 run was
bit-identical to independent native root-to-node replay for output, conv state,
SSM state, `z`, and selected winner commits. Same-process XPU-event timing used
20 warmups, 100 samples, and 16 reusable calls per sample:

| shape | depth-batched median ms/layer (4-card range) | whole-tree median ms/layer (4-card range) | decision |
| --- | ---: | ---: | --- |
| 16 rows / 6 depths | `0.14396` to `0.16304` | **`0.08816` to `0.09280`** | win; about `2.7-3.4 ms` saved over 48 GDN layers |
| 33 rows / 7 depths | **`0.26926` to `0.26970`** | `0.28592` to `0.28633` | loss; row loop loses occupancy, keep closed |

The paired four-card result supersedes frequency-sensitive standalone timing.
It also makes the boundary explicit: use the whole-tree op for the selected
16-row topology, not as a universal replacement for depth batching.

Raw reports are the `qwen27-gdn-tree-native-tree-loop-row16-gpu[0-3]` and
`row33-gpu[0-3]` JSON files under
`data/qwen36-27b-autoround-int4-b70-diagnostics/`. These are kernel diagnostics,
not endpoint throughput or LocalMaxxing evidence.

## Next integration gate

Row 16 advances. The next implementation must carry DFlash/DDTree parent,
depth, and active-node metadata through vLLM, invoke this op in every GDN
layer, verify all candidate rows with the unchanged AutoRound INT4 target, and
commit only the target-selected winner state. Completion of that gate requires
an integrated step-cost and exact-token probe; only then is a strict fresh
endpoint run justified.
