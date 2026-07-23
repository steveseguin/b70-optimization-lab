# Laguna routed-W1 N128 component and counter gate

Date: 2026-07-23 America/Toronto

Status: **pass**. The preregistered four-card exactness, matched timing, counter,
spill, and full-path name/count gates all passed. This result permits a
separate endpoint preregistration; it is not endpoint throughput evidence and
does not itself authorize a service or LocalMaxxing submission.

## Frozen identities

- Preregistration: main commit `e70b1303a`.
- Component harness implementation: main commits `543fc2b1f` and `8f2345e45`.
- Counter/full-path analyzer and trace mode: main commit `00ceeac8d`.
- vLLM: `8936aac144929190c1e53f8b8624ca397ce16f5b`.
- XPU kernels: `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`.
- `_xpu_C.abi3.so` SHA-256:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`.
- `libgrouped_gemm_xe_2.so` SHA-256:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`.
- Real route-fixture artifact SHA-256:
  `478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6`.
- PTI unitrace 2.4.0 source:
  `a5bab309f4ffdd78bd127035c46f5f75371160f8`.
- PTI unitrace binary SHA-256:
  `5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`.

## Four-card raw exactness and timing

Every physical card passed 64 changing exactness epochs before timing and 64
after timing. All local-route raw BF16 W1 values, post-SiLU/multiply values,
unchanged N64 W2 scratch, and final gathered outputs were bitwise identical.
Inputs remained immutable, N128 repeated deterministically, remote scratch
remained unwritten, M=1 through M=7 retained N64, and every forbidden N128 or
invalid-tile contract raised.

Every card then won all 31 of the preregistered A-B-B-A timing blocks:

| Physical card | Wins | Paired saving per 47 W1 calls | Relative improvement |
|---:|---:|---:|---:|
| 0 | 31/31 | 0.561977 ms | 8.6909% |
| 1 | 31/31 | 0.575211 ms | 8.6192% |
| 2 | 31/31 | 0.602729 ms | 9.1014% |
| 3 | 31/31 | 0.592822 ms | 8.4970% |

The four-card mean relative W1 improvement is **8.7271%**, above the frozen 2%
gate. Every card exceeds both its 24/31 win gate and 0.15-ms saving gate.

Aggregate:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-formal2-aggregate-c59aaad-8f2345e-20260723T053000-0400/summary.json
SHA256 bb48793e711cdb20889e888092344d35f0f3c7cb0e85bc120f63f51cff39b932
```

Per-card result SHA-256:

| Card | Result SHA-256 |
|---:|---|
| 0 | `753a0f9cddca015f8a7505be4ec3220a422cf230bb293e097fefdf4614594fc6` |
| 1 | `5189be770962212d563afa910d3b8b4cb6e8ec53b0199011f17e4e3da47457c9` |
| 2 | `0d9577cf73269dd8f229cc162fd08d9e38e7b1ce041672f8419cfb44194cc068` |
| 3 | `c5ee9c93cad1ec317bcab4d561a6df48f928aefa56ceee10fe2e747e096fb158` |

## Matched ComputeBasic counters

Each physical card used a separate N64-N128-N128-N64 sequence. Each arm had
one explicit warmup followed by 12 selected W1 calls, with a device completion
boundary after every call. The reduction exactly matches the published
route-interleave counter precedent: validate 13 selected W1 rows, discard the
explicit warmup and first settling query, then arithmetic-mean rows 2 through
12.

| Card | N64 -> N128 query time | Improvement | EU active | Stall | Occupancy | DRAM bytes | LSC bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 140.095 -> 127.903 us | 8.702% | +2.484 pp | -2.195 pp | -0.060 pp | +0.281% | -1.186% |
| 1 | 147.819 -> 137.798 us | 6.780% | +2.008 pp | -1.630 pp | -0.490 pp | +0.363% | -1.161% |
| 2 | 153.261 -> 143.057 us | 6.658% | +1.995 pp | +0.578 pp | +0.869 pp | +0.119% | -1.154% |
| 3 | 160.812 -> 146.784 us | 8.723% | +3.344 pp | -1.729 pp | +0.316 pp | +0.310% | -1.166% |

The mean counter-time improvement is **7.7158%** and the worst card is still
6.6578%. Mean EU activity rises 2.4579 points, mean stall falls 1.2442 points,
and mean occupancy rises 0.1585 points. The maximum DRAM-byte increase is only
0.3634%; LSC read bytes fall on all cards.

All reports have zero uncertainty, split, overrun, loss, inconsistency, and
mid-query flags. Every N64 query reports 1,280 workgroups times four
subgroups; every N128 query reports 640 workgroups times eight subgroups. Both
therefore retain exactly 5,120 output-owning subgroups. Every arm has:

- zero compiler-reported spill memory per thread;
- zero load/store-cache writes and partial writes;
- zero SLM allocation, traffic, and bank conflicts; and
- identical production int32 route-interleaved arithmetic identity except for
  the existing W1 policy template and launch shape.

## Runtime W2 and gather proof

The isolated counter mode deliberately contains W1 only, so it cannot prove
the separate W2/gather call-count requirement. A matched full routed-path trace
was therefore collected on all four cards. In both N64 and N128 arms on every
card, unitrace reports exactly:

- 13 W1 calls;
- 13 calls to
  `GemmM8TopkInt4CuteName<int, w4a16_policy_m_8, true>` with
  3,840 N64 workgroups; and
- 13 calls to the same BF16 `MoeGather<...,10,8>` kernel.

The full W2 and gather names are byte-identical between N64 and N128 on every
card. Separately, the native W2 launcher block and Python route-parallel
W2/gather block are byte-for-byte identical between the approved baseline
kernel commit `b6076ce1` and candidate `c59aaad`; their block SHA-256 values are
`7b78e141e4a320ed0f46f01ff40cdcff5e93144ac31b8642bee079eb8ceb4bc6`
and
`2366da88662bf9d0b346efc5f720df11139c543c5b387b3d993efbd3e0cc8784`.

Counter and trace aggregate:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-counter-gate-c59aaad-00ceeac-20260723T054500-0400/summary.json
SHA256 677b69fe353056a8a7a9afff7e7e952fe337a6d605c326beb80ae5e0103b6e76
```

## Preserved profiler failure

The first full-path trace attempt added `--follow-child-process 0` to avoid
small timing-only files from the harness's physical-device probe. PTI unitrace
segfaulted before the application or a GPU kernel started and produced an
empty harness log. All cards remained idle. The failed attempt is preserved
at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/w1-n128-full-path-trace-card0-c59aaad-00ceeac-20260723T052000-0400/
```

The formal traces used unitrace's historically proven default child handling.
The complete trace is selected by its three routed-kernel families; the extra
98-byte child timing files are excluded by the fail-closed analyzer.

## Disposition

N128 passes the entire preregistered component/counter lane without changing
arithmetic, routing, W2, gather, attention, DFlash, model weights, or any M<8
tail. The next allowed action is a separate committed endpoint
preregistration against the approved 33.89498511171744-tok/s stack. No service
was started and no LocalMaxxing request was made during this component gate.
