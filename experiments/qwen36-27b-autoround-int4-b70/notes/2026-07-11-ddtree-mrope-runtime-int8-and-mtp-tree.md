# Qwen27 DDTree M-RoPE repair, runtime-INT8 closure, and MTP-tree lane

Date: 2026-07-11

Status: diagnostic research only. The promoted strict-fresh record remains
`68.23626314761921 tok/s`; none of the runs below passed the full quality and
variance promotion gate, and none should be submitted to LocalMaxxing.

## DDTree acceptance repair

Full-context DFlash reconstruction showed that incremental draft KV was not the
endpoint acceptance defect. A target-hidden dump instead exposed a positional
identity mismatch: Qwen3.6 target M-RoPE columns were populated by physical
tree-row order, while a tree node's logical position is its depth. The target
runner now remaps M-RoPE/XD-RoPE columns by `depth_indices` while retaining
unique physical KV slots.

After the repair, endpoint and offline acceptance aligned:

- endpoint mean accepted draft nodes: `2.60909`;
- offline mean visible depth: `2.56364`;
- endpoint-minus-offline mean: `+0.04545`;
- exact agreement: `90.91%`.

This is an acceptance/correctness repair, not a speed record.

## Corrected cold endpoint screen

The repaired target ran the fixed realistic suite once per prompt with
`cached_tokens=0` and quality deliberately skipped:

| DDTree nodes | median tok/s 1-100 | mean | p10 |
|---:|---:|---:|---:|
| 4 | `57.6397` | `55.9266` | `49.8350` |
| 8 | `56.1260` | `56.9016` | `51.4908` |
| 12 | `57.8505` | `56.8214` | `50.4396` |
| 15 | **`59.0053`** | `57.8427` | `50.9368` |

Evidence is under
`data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-ddtree-depthrope-k*-20260711T075901Z.json`.
The 15-node profile averaged roughly `13.529 ms` in DFlash drafting per target
step: forward `6.334 ms`, draft LM head `3.623 ms`, target-logit-related draft
work `3.574 ms`, input construction `1.128 ms`, top-k `0.685 ms`, context
projection `0.264 ms`, log normalization `0.227 ms`, and rejection sampling
`0.240 ms` (some regions overlap, so do not sum every label independently).

A wider tree did not help. The 23-node lane was valid/fresh/cached-zero but fell
to `56.0807584460932 tok/s` median (`54.4966` mean, `48.9424` p10). Nodes 31
and 47 exceeded the available KV-memory budget at `max_model_len=2048`
(`6.32/9.77 GiB` required vs `5.78 GiB` available). The repeated 15-node lane
hit a stale AOT graph from the runtime-INT8 experiment and failed with
`KeyError: weight_scale`; this established that compiler-cache identity must
include runtime quantization method, not only shapes and model revision.

## Real-weight DFlash query-body INT8 experiment

Reusable benchmark:

- `scripts/bench-dflash-runtime-int8.py`;
- `scripts/run-dflash-runtime-int8-microbench-4gpu.sh`;
- stamp `20260711T081826Z` under
  `data/qwen36-27b-autoround-int4-b70-diagnostics/`.

It uses real DFlash weights and shapes for FC `[5120,25600]`, QKV
`[6144,5120]`, O `[5120,4096]`, gate/up `[34816,5120]`, and down
`[5120,17408]`, at rows 4/8/16. At 16 rows, online activation quantization plus
W8A8 GEMM with FP32 scales beat BF16 GEMM in isolation:

| projection | W8A8 ms | BF16 ms | isolated speedup |
|---|---:|---:|---:|
| QKV | `0.0876` | `0.1593` | `1.82x` |
| O | `0.0740` | `0.1160` | `1.57x` |
| gate/up | `0.4257` | `0.6813` | `1.60x` |
| down | `0.3001` | `0.3545` | `1.18x` |
| FC | `0.4371` | `0.5170` | `1.18x` |

FP32 scales had relative RMSE around `1.25-1.7%` and cosine near `0.9999`.
BF16 scales were numerically invalid for these body shapes (NaNs or extreme
error) despite similar timing. The projected whole-body saving was only about
`2.2 ms/step`, already too small to turn the 59 tok/s DDTree lane into a record.

A default-off query-body integration was nevertheless tested. It initially
failed because the custom quant method lacked fake registration, then loaded
and compiled after registration. Replacing buffers with frozen parameters
reduced loaded model memory from `23.74` to `20.52 GiB`, but an eight-token
endpoint smoke still took `33.740 s` (`40.596 s` for the buffer variant).
Opaque W8A8 custom ops interacted catastrophically with the AOT/FULL endpoint;
the lane is closed as an endpoint no-win. Source was reverted after preserving:

- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-dflash-query-runtime-int8-no-win-20260711.patch`;
- SHA-256:
  `ab323a203ed0d6fc44100e0d675850ad5f1f3c2c5e5dee1cd7e1b9edbc003174`.

The patch is a composite `qwen3_dflash.py` delta over the already modified
local tree, not an upstream-ready isolated change.

## Xe2 DPAS W4A16 target-body screen

The existing grouped Xe2 DPAS W4A16 kernel was tested as a one-expert dense
kernel with the real Qwen27 projection shapes and correct two's-complement
INT4 unpacking. Early unsigned/signed test data had made the kernel look
promising; that representation was invalid and is not performance evidence.

The corrected rows=4 cross-GPU run (`20260711T091813Z`) was stable and a clear
no-win. Even the closest projection, GDN QKVZ `[4,5120] x [5120,16384]`, was
slower than the oneDNN dense baseline on every B70 (`0.913-0.926x`). Projected
across the measured Qwen target projection call counts, oneDNN required
`22.57-22.68 ms/step` while the Xe2 path required `31.74-31.99 ms/step`
(`0.707-0.711x`). Numerical comparison was finite with max absolute error at
most `0.03125` for the measured projections.

Artifacts:

- benchmark: `scripts/bench-qwen27-w4a16-xe2-dense.py`;
- four-GPU harness:
  `scripts/run-w4a16-xe2-rows4-4gpu.sh`;
- results:
  `diagnostics/qwen27-w4a16-xe2-rows4-gpu*-20260711T091813Z.json`;
- kernel experiment patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-w4a16-xe2-m16-ntile-sweep-20260711.patch`;
- patch SHA-256:
  `4e7ef12db0e5dec7d7bea0f5dd8dea9661a0d90bf80815941b5b37484d903a6c`.

Do not integrate this grouped Xe2 kernel into the endpoint. A future target
body lane needs a materially different dense W4A16 implementation or
producer/consumer fusion, not more N-tile tuning of this kernel.

## HipFire composition audit

HipFire commit `d44f89e7` uses a 15-token greedy DFlash chain plus two MTP leaf
alternatives per chain slot: 46 target rows verified once. The portable idea is
candidate composition before one ancestor-masked target pass; the HIP/MQ
kernels are not portable to XPU. Its measured hybrid added only `0.02-0.17`
MTP tokens per cycle and was 3-7x slower than linear composition, so copying
that shape is rejected.

For the local best-first DDTree, a credible composite would add only four MTP
leaves to high uncovered-probability parents (15 DFlash + 4 MTP = 19 draft
nodes). It can add at most one visible token per target step, and to beat the
current 68.236 record it needs close to `+0.9` token/step with less than about
`6.4 ms` total hybrid overhead. Measure an offline proxy-MTP oracle before
building this composite proposer.

## Intrinsic MTP fixed-tree precheck

Before paying for a DFlash+MTP composite proposer, use vLLM's existing
intrinsic-MTP fixed-tree generator to test the economics of branching. The
local arbitrary-tree target already supports logical-depth M-RoPE, ancestor
attention, branch-specific GDN state, greedy tree walking, winner-state commit,
and ordered KV compaction. The missing transport was fixed-tree parent/depth
metadata, plus accepted-path compaction before the next proposer call.

Implementation adds:

- pure breadth-first path-to-parent/depth conversion with invalid-tree guards;
- metadata export only for branching trees whose draft groups actually use
  `TREE_ATTN`;
- generic accepted-path compaction for DFlash, Eagle/MTP, and draft-model
  trees;
- six focused unit tests, all passing.

Four-GPU diagnostic harness:
`scripts/run-mtp-fixed-tree-screen-4gpu.sh`. It compares chain-3, binary depth
2 (6 nodes), binary depth 3 (14 nodes), and ternary depth 2 (12 nodes), with
isolated AOT caches and the cold realistic suite. Quality remains deferred
unless a shape beats the 68.236 record by enough to justify variance testing.

### Fixed-tree endpoint result

The screen required three generic fixed-tree repairs before it could execute:

1. `propose_tree` assumed a 1D `self.positions` buffer, but Qwen3.6 MTP uses
   three-row M-RoPE. It now preserves logical 3D positions while using M-RoPE
   row zero for physical KV slot allocation.
2. Tree code assumed an Eagle `(last_hidden, hidden)` tuple, while intrinsic
   MTP returns one hidden tensor. Return handling now follows
   `model_returns_tuple()` and passes the appropriate `spec_step_idx`.
3. The tree's level-batched MTP call hit an AOT optional-input signature bug
   (`NoneType.size`). `enforce_eager` alone disables graph replay but not the
   compiled wrapper; the tree forward context now uses `skip_compiled` when
   the diagnostic requests eager drafting. The expensive target remains FULL
   decode captured.

Failed startup/request attempts are retained at:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-screen-20260711T085904Z`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-screen-20260711T090608Z`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-screen-20260711T090911Z`.

The completed cold realistic screen is
`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-screen-20260711T091158Z`:

| shape | draft nodes | median tok/s | mean | p10 | live mean acceptance length |
|---|---:|---:|---:|---:|---:|
| chain depth 3 | 3 | `23.9378` | `23.2041` | `23.0131` | anomalous `~1.0` |
| binary depth 2 | 6 | **`58.8252`** | `58.8754` | `56.9529` | `~2.6-2.7` |
| binary depth 3 | 14 | `54.3507` | `54.8607` | `50.3980` | `~3.2` |
| ternary depth 2 | 12 | `52.9284` | `52.5659` | `50.3181` | `~2.8` |

All four completed the 12-prompt suite with each prompt once,
`cached_tokens=0`, and no history/cache reuse. Quality was skipped. The chain
control is not a valid comparison to the current serial MTP3 path: because it
is non-branching, topology export intentionally stayed off, and the combination
of static target TREE_ATTN with ordinary GDN/sampler handling produced near-zero
draft acceptance. It is useful only as evidence that fixed-tree and flat target
contracts must not be mixed.

### Audit correction: do not use the table above for an economic decision

Independent review found two P0 defects after the run completed:

1. rejected-token `seq_lens` correction occurred below the tree path's early
   return, so later proposal cycles could attend rejected/stale rows;
2. deeper tree levels sliced physical draft positions from `level` instead of
   from zero, shifting KV slots for depth-3 trees.

The first defect can affect all branching shapes after rejection; the second
affects depth-3 shapes. Grammar- or budget-truncated trees also silently lost
topology and could be verified as a flat sibling chain. Therefore the
`20260711T091158Z` speeds and acceptance lengths are retained as invalid
diagnostic history, not evidence that branching is a no-win. The code now
corrects rejected sequence lengths before entering either proposal path,
anchors accumulated queries at physical offset zero, validates regular
breadth-first trees, and drops rather than flattens truncated topology. A
corrected four-GPU rerun replaces the invalid chain lane with a second binary-2
control for a basic device/run consistency check.

### Corrected fixed-tree result

The final reviewed run completed at
`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-corrected-20260711T094303Z`:

| shape | draft nodes | median tok/s | mean | p10 | final logged mean acceptance |
|---|---:|---:|---:|---:|---:|
| binary depth 2, GPU 0 | 6 | `58.8914` | `59.2665` | `57.6748` | `2.72` |
| binary depth 2, GPU 1 | 6 | `58.8985` | `59.2659` | `57.5083` | `2.72` |
| binary depth 3 | 14 | `54.4225` | `54.8037` | `51.7869` | `3.33` |
| ternary depth 2 | 12 | `53.1331` | `53.4206` | `52.0841` | `2.84` |

All lanes completed the 12 cold prompts once with `cached_tokens=0`; quality
was intentionally skipped because every shape was well below the promoted
record. The duplicated binary-2 medians differ by only `0.012%`, and their
acceptance is effectively identical, so the no-win is not a temperature/device
variance artifact. Binary depth 3 confirms the economic limit: more branches
raised accepted depth to `3.33`, but verifying 15 root-plus-node rows made it
slower than binary depth 2 and the serial MTP3 record.

The earlier `20260711T092413Z` run produced the same conclusion but preceded
the final alias/grammar review guards. It is retained as diagnostic history,
not the final evidence. A `20260711T093849Z` rerun was intentionally
interrupted during startup after noticing that aliased metadata CPU shadows
also needed invalidation; no result from that attempt is used.

Regular intrinsic-MTP trees are now closed on corrected evidence. Preserve the
generic transport/correctness patch for future models, but do not spend more
Qwen27 endpoint sweeps on nearby regular shapes.

The refreshed source snapshot is
`patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-ddtree-mrope-fixedtree-composite-wip-20260711.patch`
(SHA-256
`585d0c45b54f57116ee2b168c92f1bc39c9d2ed5517f3c0711c7f1eda8929a56`).
It is deliberately labeled **composite WIP**: the vLLM research worktree also
contains the prerequisite ReplaySSM/DDTree stack and other preserved XPU
experiments, so this is a durable exact source snapshot rather than an
upstream-ready isolated patch.

A post-run independent review added three guards before snapshotting: aliased
per-KV-group `seq_lens` views are adjusted only once, structured-output grammar
requests drop branching speculation because the existing validator is serial,
and each breadth-first level must be globally parent-major. Focused topology,
aliasing, scheduler-budget, malformed-topology, and structured-output tests
pass `16/16`.

## Next decision

1. Regular intrinsic-MTP trees are closed from the corrected four-GPU run; do
   not use the invalid `20260711T091158Z` table as supporting evidence.
2. Build the 15+4 DFlash/MTP composite only if its offline oracle predicts at
   least `+0.35` visible token/step; challenging the record likely needs much
   more.
3. Promotion still requires exact canaries, repeat64, 1K needle, baseline
   comparison, strict fresh/cached-zero suite, and same-window/crossover when
   movement is within variance.
