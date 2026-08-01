# Laguna transposed-scale prefetch-distance component screen

Date: 2026-07-31 America/Toronto

Status: **stopped as timing-inconclusive/null at component gate; no endpoint
authorized**.

## Premise

The confirmed record changed target decode scale storage from strided
`[expert,N,K/32]` to contiguous `[expert,K/32,N]`. Historical prefetch-distance
measurements predate that layout change and therefore do not establish the
best distance for the current record. The immediately preceding removal screen
proved that scale prefetch is essential: deleting it was 31.2568% slower while
remaining bitwise exact.

The existing record DSO already exposes the fail-closed literal
`VLLM_XPU_LAGUNA_PREFETCH_DIST={3,6,12}`. This screen changes no source or
binary. It asks whether the new contiguous scale layout changes the optimum
when scale and packed-weight prefetch retain their currently coupled distance.

## Frozen component contract

- DSO SHA-256:
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- source: `8dd94f2307db3b830fe07f212c4b36f719652a5c`;
- rank 1 only, one fresh worker per arm;
- GRF128, transposed scales, `SCALE_VEC=1`, `DEQUANT_MAD=0`,
  `SCALE_FOLD=0`;
- deterministic changed-input W13 `N=2048,K=3072,M=120` and W2
  `N=3072,K=1024,M=120` cases;
- distance 6 is the control; distances 3 and 12 are candidates;
- compare raw BF16 output hashes for all six changed-input outputs.

## Gates

1. Require logical inputs and raw BF16 outputs to match the distance-6 control
   6/6 for each candidate.
2. Stop if neither candidate improves the summed W13+W2 median by at least
   1.0%, if either real shape regresses by more than 1.0%, or if the nine-sample
   timing distributions make ordering unclear.
3. A component pass only identifies a candidate. Any full-model run requires a
   separately recorded endpoint gate using the unchanged cold 13-prompt suite.

No target/draft precision, BF16 KV, prompt, teacher, acceptance, topology,
cache, warmup, retry, metric, or quality contract may change. No reset, reboot,
or privileged recovery is authorized.

## Result

Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scale-prefetch-distance-component-8dd94f2-20260801T0200Z`

All three workers loaded the same expected DSO and recorded their requested
distance. Logical inputs matched and distances 3 and 12 were raw-BF16 exact
against distance 6 on all six changed-input outputs.

| distance | W13 median | W2 median | summed vs 6 | exact |
|---:|---:|---:|---:|---:|
| 6 | 0.3209162 ms | 0.1921288 ms | 1.000000x | control |
| 3 | 0.3208000 ms | 0.18258645 ms | 1.019187x | 6/6 |
| 12 | 0.3208536 ms | 0.1906220 ms | 1.003068x | 6/6 |

The table's apparent distance-3 pass is not admissible. W2 was bimodal within
each worker: after eight unrecorded warmups, the distance-6 samples changed
from about 0.192 ms to 0.182 ms after sample five; distance 3 made the same
transition earlier, and distance 12 made it after sample five. Stable-tail W2
samples overlap at roughly 0.182--0.183 ms. W13 is stable but all three medians
differ by less than 0.04%. This triggers the preregistered “ordering unclear”
stop rather than authorizing an endpoint.

The evidence closes a coupled-distance endpoint claim. It does not test the
narrower hypothesis that weights should remain at distance 6 while only the
small contiguous scale line moves closer. That requires a new compile-time
candidate and a measurement protocol which warms each shape to its stable
timing regime before comparison.
