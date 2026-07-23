# Laguna exact M=8 routed-W1 N128 preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: hypothesis, implementation boundary, component gates,
and endpoint boundary frozen before source changes, native rebuilds, or GPU
work. Three independent read-only audits ranked this as the cleanest remaining
occupancy experiment.

## Frozen starting point

The approved exact stack is:

- LocalMaxxing record `cmrx6p5dv001bo4017hb7sixz`;
- conservative eligible throughput `33.89498511171744 tok/s`;
- target-cycle median `88.886261 ms`;
- `3.694186` emitted tokens per target cycle;
- main repo `cf2a7d24cf5eb9bf7cfd1b494212142d689be6e1`;
- vLLM repo `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU-kernels repo `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- DFlash depth 7, exact target verification, eager execution, TP4/EP4,
  concurrency 1, and the approved shared-elementwise plus QKNorm/RoPE stack.

The current route-interleaved W1 estimate is `6.250323 ms` per 47-layer target
cycle. Matched counters measured `47.723%` EU active, `86.666%` thread
occupancy, and about `502.278 GB/s` of reads. This is not a claim that half of
W1 is removable: the measured read rate is already about 86.7% of the
579-GB/s card figure. The experiment targets only scheduler and route-return
overhead around that bandwidth-bound work.

## Single frozen treatment

The incumbent M=8 W1 policy is:

```text
workgroup tile M8 x N64 x K32
1280 workgroups x 4 subgroups = 5120 subgroups
```

The only candidate is:

```text
workgroup tile M8 x N128 x K32
640 workgroups x 8 subgroups = 5120 subgroups
```

Both policies already exist in the source tree. N128 halves the number of
workgroups while retaining the same 5120 output-owning subgroups, K32
traversal, group-32 INT4 dequantization, FP32 DPAS accumulation, independent
routed rows, and BF16 stores. It must not change expert routing, gate/up column
ownership, SiLU arithmetic, W2, gather, collectives, DFlash, attention, or any
model weight.

N32 is forbidden in this experiment. It may be considered only after this lane
is completely classified and a new preregistration is committed before any
N32 build or measurement. There is no adaptive tile sweep and no selection
from endpoint results.

## Fail-closed selector and source boundary

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_W1_N_TILE=128
```

Unset or literal `64` selects the incumbent. Only decimal `64` and `128` are
valid. Any other value must raise during model construction.

The native operation receives a required trailing integer `w1_n_tile`; it has
no schema default. N128 must raise unless all of these are true:

- the exact Laguna INT4/BF16 MoE path is enabled;
- fused W1 plus route-parallel W2 is enabled;
- route interleave is enabled;
- the operation is in W1-only mode;
- there are exactly eight input rows and ten routes per row;
- local/global experts are 64/256 under EP4; and
- there is no routed clamp or rejected remote-zero mode.

Production dispatch passes N128 only for the matching M=8 target call. M=1 and
M=2..7 verifier tails pass literal N64 even when the selector is enabled.
Prefill, draft, fused-transaction mode, other models, other dtypes, other
shapes, graph paths, and generic grouped GEMMs remain on their literal existing
paths. An intentional native call with N128 outside the declared contract must
raise rather than fall back.

The runtime integer may only select between the existing
`w4a16_policy_m_8` and `w4a16_policy_m_8_n_128` W1 launcher templates. The W2
launcher and route-parallel W2 call remain N64. Both the grouped-GEMM library
and `_xpu_C` extension must be rebuilt and installed together because the
required native signature changes.

## Four-card raw-exact component gate

Run one process per physical B70 with one visible Level Zero device. Every
card must pass independently.

Each card gets at least 64 changing M=8 epochs. Across the epochs, change:

- BF16 hidden states;
- packed INT4 W13 weights;
- BF16 W13 scales; and
- route tables covering local, remote, duplicate, rank-boundary, expert 0,
  expert 63, expert 64, and expert 255 cases.

For each epoch, run N64 and N128 from identical immutable inputs into separate,
explicitly initialized scratch. Require:

- raw `uint16` equality and `torch.equal` for every local-route W1 value in
  `[80,2048]`;
- raw equality for every local-route BF16 SiLU/multiply value in `[80,1024]`;
- identical results after feeding each activation through the same incumbent
  N64 W2, including local W2 scratch and final gathered `[8,3072]` output;
- unchanged hashes for hidden states, weights, scales, routes, and top-k
  weights;
- N128 repeat determinism; and
- a complete 64-epoch post-timing replay.

Remote W1 and activation rows are deliberately unwritten and are not compared.
Both arms must zero W2 scratch before the unchanged W2 call because the gather
reads remote route slots.

The harness must also cover M=1 through M=7 with production-effective N64 and
prove raw equality to the selector-disabled result. Direct N128 calls for
M=1..7, route-interleave off, W1-only off, and invalid tile values must all
raise. One mismatch or one missing rejection fails the lane before profiling
or endpoint work.

## Frozen matched timing and counter gate

Time isolated fused W1 plus its exact BF16 activation only. Do not include
fixture generation, allocations, hashing, W2, gather, CPU work, or
synchronization inside an arm. Both arms use route interleave and differ only
in the W1 tile template.

On every card:

- warm both arms for 20 complete 47-layer cycles;
- run 31 alternating A-B-B-A blocks;
- execute 64 complete 47-call cycles per arm per block;
- rotate a prepared changing fixture outside the timed arm;
- synchronize only at arm boundaries; and
- repeat the complete exactness corpus after timing.

N128 advances only if, on every card, it:

- wins at least 24 of 31 paired blocks;
- saves at least `0.15 ms` per 47-layer cycle at the paired median; and
- has a strictly positive mean improvement.

Across the four card medians, the mean relative W1 improvement must also be at
least 2%. Do not average away a failing card.

After a timing pass, collect matched isolated hardware counters with a device
completion boundary after every selected kernel. The profile must prove that:

- only the W1 policy template changes from N64 to N128;
- W2 and gather kernel names and call counts remain identical;
- total W1 subgroup/output ownership remains 5120; and
- there is no material read-bandwidth, stall, spill, or occupancy regression
  inconsistent with the measured wall-time win.

If timing passes but counters are ambiguous, preserve the exact/timing result
as inconclusive and stop before an endpoint.

## Endpoint boundary

No endpoint run is authorized by this note alone. If and only if every
component and counter gate passes, commit a separate endpoint preregistration
before starting a service.

That note must freeze a fresh cold A-B-B-A comparison against the approved
33.894985-record stack, with:

- the fixed 13-prompt suite, each prompt once per fresh service;
- one active generation and no prefix/cache/history reuse;
- `cached_tokens=0` for all 52 requests;
- exact returned token IDs against the canonical q=1 greedy teacher;
- full 512-token generations, long-to-next and rollover canaries;
- median generated-token throughput over tokens 1 through 100 after TTFT;
- both adjacent candidate pairs winning at least 9/13 prompt rows;
- at least `0.15 ms` paired target-cycle saving;
- absolute acceptance-rate change no greater than `0.001`; and
- the conservative lower candidate throughput exceeding both the lower
  control and `33.89498511171744 tok/s`.

There is no fifth rescue leg. A LocalMaxxing submission is allowed only for a
real matching-identity record that passes every exactness and honesty check.
All build logs, component JSON, counter captures, service logs, endpoint
summaries, teacher comparisons, and submission responses must be preserved
under the tracked experiment ledger or
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/`.
