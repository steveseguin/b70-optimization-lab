# MTP1 M=2 gather/shared-add gate

Date: 2026-07-16

## Outcome

A fixed-M2 kernel that fuses generic routed gather with the following
shared-expert BF16 addition is bitwise exact and improves every measured route,
but the real route-direct package remains below the frozen
`0.50 ms/43 layers` every-route gate. It was not service-tested.

The frozen model, TP4+EP topology, MTP1 policy, FP8 KV cache, and quantization
did not change. The verified one-session decode record remains
`63.349927998683015 tok/s`, LocalMaxxing `cmrncv39w003ylg01hogleazo`. No
LocalMaxxing submission was made.

## Exact arithmetic

The fused kernel preserves the unfused chain's rounding contract:

`FP32 routed accumulation -> BF16 -> add shared BF16 -> BF16`.

All variants pass `84/84` changed-input graph cases, including overlap,
same-token duplicates, all-duplicate, six-local, all-remote, and changing
shared outputs.

## Real route-direct result

The initial fused kernel projects:

| Route | Saving / 43 layers |
|---|---:|
| same typical | 0.650631 ms |
| disjoint typical | 0.747987 ms |
| cross-row overlap | 0.762498 ms |
| within-row duplicate | 0.902763 ms |
| all duplicate | 0.640860 ms |
| six local | 0.535187 ms |
| all remote | 0.447916 ms |

The all-remote rank is the fail-closed minimum. A uniform empty-routed fast
path avoids loading weights and executing the six-way routed accumulation when
all map entries are `-1`. It raises all-remote to `0.470119 ms`, but six-local
then sits at only `0.501110 ms`; the package still fails and has no robust
local margin.

Caching the six route IDs and weights through subgroup broadcasts is a
preserved loss. It lowers all-remote to `0.403419 ms` and six-local to
`0.517701 ms`: the route metadata is already cache-hot and broadcast
instructions cost more than the redundant loads.

## Combined deletion ceiling

Literal deletion of remap plus fused gather/shared-add passes twice:

| Run | Worst route | Minimum saving / 43 layers |
|---|---|---:|
| 1 | all remote | 0.504173 ms |
| 2 | all remote | 0.523872 ms |

This is an informative upper bound, not an implementation result. The weaker
run leaves only `0.004173 ms/cycle`, or `0.097 us/layer`, for a real remap-free
GEMM1 implementation.

After adding the empty-routed fast path to the deletion ceiling, the corrected
upper bound passes twice at `0.538451` and `0.527472 ms/43 layers`, again with
all-remote as the minimum. This is the ceiling used for the unique-route
screen below. It leaves only `0.638-0.894 us/layer` for every new route-table
operation and any downstream consumption overhead.

## Why literal source-direct GEMM1 is not funded

The exact grouped A row order for one expert is
`[token0 repeated c0][token1 repeated c1]`. Cross-token unique rows are affine,
but duplicate cases such as `[0,0,1]` and `[0x6,1x2]` are not. Xe block2D
requires one rectangular affine surface and cannot express a per-row index
vector. Scalar gathers, two block2D loads, SLM staging, or splitting at the
token boundary repeat work across every output-N tile and cannot fit the
`0.097-0.555 us/layer` measured allowance.

The broader exact redesign is to deduplicate identical `(token, expert)`
routes once upstream. Each expert then has at most affine rows `[token0]`,
`[token1]`, or `[token0,token1]`; gather retains distinct route weights and may
reuse one expert output row for duplicate slots. The route table must be
produced in an already-running M=2 router/top-k boundary and consumed by both
GEMMs and fused gather/add. A new launch would erase the ceiling.

## Unique-route router screen

That broader redesign is now implemented and performance-closed before
downstream integration. The opt-in M=2 router preserves the original weights
and IDs bit-for-bit while emitting encounter-ordered unique experts, per-expert
token masks, original-slot-to-unique mapping, and a unique count. Forty eager
changing inputs and 32 changing graph replays are exact for every emitted
field.

The implementations reduce the route-table overhead as follows:

| Emitter | Overhead / layer | Overhead / 40-layer cycle |
|---|---:|---:|
| lane-0 serial table | 6.509 us | 0.260 ms |
| 12-lane global table | 4.691 us | 0.188 ms |
| local route staging | 4.301 us | 0.172 ms |
| local staging + subgroup ballot | 3.132 us | 0.125 ms |
| WG32/local barrier shell, no table | 0.076 us | 0.003 ms |

The shell proves that packing the two SG16 routers into one WG32 and crossing
the required local barrier is not the blocker. Stable deduplication, prefix
ranking, token-mask construction, slot mapping, and output stores cost
`3.132 us/layer` even in the best exact implementation. Subtracting its
`0.125285 ms/cycle` cost from the two fast-path deletion ceilings leaves only
`0.413166` and `0.402188 ms/cycle`, both below the frozen `0.50 ms` integration
gate before either compact GEMM consumes the table. Cards 1-3 and the service
were therefore not run.

The upstream unique-route representation is closed in its current form. A
future retry needs a materially larger jointly deleted boundary or a route
representation consumed directly inside an already-expensive downstream
kernel; another router-side table emitter cannot fit this measured ceiling.

## Preserved source and evidence

- XPU branch: `codex/deepseek-v4-m2-gather-shared-add`
- exact fused kernel: signed XPU commit `820ecc5`
- rejected subgroup-broadcast experiment/revert: `576251b` / `ba5ed8d`
- empty-routed fast path: signed XPU commit `4e2ce07`
- unique-route branch: `codex/deepseek-v4-m2-unique-routes`
- serial emitter: signed XPU commit `e7685b1`
- parallel global emitter: signed XPU commit `9360422`
- local-memory emitter: signed XPU commit `579db66`
- subgroup-ballot emitter: signed XPU commit `c71bd3e`
- WG32/local-barrier floor and exact restore: signed XPU commits
  `fdc4765` / `70e3824`
- restored subgroup-ballot `_xpu_C` SHA-256:
  `a680c78a1a335ab54e8d1046e12de9bfd5f1c59db5dc5529c27676954445c559`
- initial fused `_moe_C` SHA-256:
  `1259d1ee2874b97e39731986c3a1f84cf3d17ac40017fa19f0fb90f8a4799cf2`
- empty-routed `_moe_C` SHA-256:
  `b8fbb7dbafc4b195656916e006861d065cb11ab6dec596964aa769cdb7508d41`
- raw results: `data/deepseek-v4-reap-mxfp4-m2-gather-shared-add-20260716/`
- route-table benchmark:
  `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-m2-router-unique-routes.py`
- route-table raw results:
  `data/deepseek-v4-reap-m2-router-unique-routes-20260716/`

Do not service-test either kernel as a standalone patch. No measured
noncollective M=2 source boundary now clears the `0.50 ms/cycle` gate. Resume
only with a new architectural boundary and a fresh exact upper-bound proof.
