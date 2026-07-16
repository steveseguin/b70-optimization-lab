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

## Preserved source and evidence

- XPU branch: `codex/deepseek-v4-m2-gather-shared-add`
- exact fused kernel: signed XPU commit `820ecc5`
- rejected subgroup-broadcast experiment/revert: `576251b` / `ba5ed8d`
- empty-routed fast path: signed XPU commit `4e2ce07`
- initial fused `_moe_C` SHA-256:
  `1259d1ee2874b97e39731986c3a1f84cf3d17ac40017fa19f0fb90f8a4799cf2`
- empty-routed `_moe_C` SHA-256:
  `b8fbb7dbafc4b195656916e006861d065cb11ab6dec596964aa769cdb7508d41`
- raw results: `data/deepseek-v4-reap-mxfp4-m2-gather-shared-add-20260716/`

Do not service-test this kernel as a standalone patch. Continue only with an
end-to-end upstream-produced unique-route representation and require its real
complete chain to clear the same every-route gate twice before cards 1-3.
