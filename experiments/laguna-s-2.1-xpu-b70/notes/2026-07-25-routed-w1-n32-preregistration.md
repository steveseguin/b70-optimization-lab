# Laguna routed-W1 N32 occupancy preregistration

Date: 2026-07-25 America/Toronto

Status: preregistered before implementation; no candidate binary, XPU
component run, model generation, endpoint campaign, payload, or submission has
started.

## Objective

Test whether the existing Xe2 `M8 x N32 x K32` INT4 policy improves routed-W1
workgroup occupancy for the exact Laguna S 2.1 M=8 verifier. The incumbent uses
`M8 x N64 x K32`; the closed N128 endpoint treatment used
`M8 x N128 x K32`.

For Laguna's 80 routed rows and W1 width 2048:

- N32 launches 2,560 workgroups with two SIMD32 subgroups each;
- N64 launches 1,280 workgroups with four SIMD32 subgroups each; and
- N128 launches 640 workgroups with eight SIMD32 subgroups each.

All three geometries therefore retain 5,120 output-owning subgroups. The
candidate changes workgroup packing and scheduling only. It must not change
the K32 accumulation chain, BF16 SiLU, W2, route order, gather, reduction,
attention, collective, graph, or speculative-decoding arithmetic.

## Why this lane is distinct

N32 is implemented as `w4a16_policy_m_8_n_32` but has not been measured in the
Laguna routed-W1 production path. The N128 treatment is terminal after an
exact endpoint loss of 2.6890% and only 3/13 paired row wins. N32 is a separate
narrower geometry, not a retry of N128.

The down-only and gate/up shared-expert native-M8 lanes are also terminal after
their cold-counter gates failed despite component wins. Gather-sharded and
gather-finalize are closed under their frozen preflight protocols. None of
those selectors may be enabled or repaired in this experiment.

A proposed attention-metadata sharing follow-up was rejected before
preregistration: the model runner already builds metadata once per compatible
KV-cache/builder group and maps the same object to every layer in that group.
The 48 profiled attention boundary calls are attention executions, not 48
independent persistent-metadata refreshes.

## Frozen source and record identity

The implementation starts from:

- main repository record head:
  `3bb7513f1cfafb41146e1161904ca784376a356a`;
- vLLM:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`; and
- matched DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`.

The matching approved record is `94.92003934159611 tok/s`,
LocalMaxxing `cmrzrd4tf001ipa013xpx4kid`.

All live model, build, cache, temporary, log, run, and evidence paths must be
on internal NVMe/ext4 under `/mnt/fast-ai`. The external Corsair USB is
backup-only and must not be a live dependency.

## Sole treatment

The control is literal:

```text
VLLM_XPU_LAGUNA_M8_W1_N_TILE=64
```

The candidate is literal:

```text
VLLM_XPU_LAGUNA_M8_W1_N_TILE=32
```

Implementation may only:

- add literal 32 to the existing strict W1-tile parser;
- require the same exact batched-MoE, fused-W1/route-W2, route-interleave,
  M=8, W1-only, and EP4 expert-map contract used by N128;
- select the existing `w4a16_policy_m_8_n_32` template for candidate W1; and
- extend focused parser, effective-tile, native-contract, and dispatch tests.

Literal 64 remains the default. M=1 through M=7 must force N64 even when 32 is
configured. W2 must remain N64. The op schema and all tensor shapes, dtypes,
views, buffers, arguments, and launch count remain unchanged. Invalid tiles
and any candidate use outside the exact M=8 W1-only contract must fail closed.

No vLLM behavior change is authorized unless implementation proves that the
existing kernel-package selector cannot express this exact treatment.

## Gate 1: static and CPU-only

Before a native build:

- focused parser/effective-tile/schema tests pass;
- source inspection proves N32 is selected only for eligible M=8 W1;
- deliberate N32 misuse without exact batched MoE, fused-W1/route-W2, route
  interleave, or EP4 map is rejected;
- M=1 through M=7 resolve to N64;
- W2 and gather dispatch remain N64 and unchanged; and
- formatting, lint, whitespace, and repository status checks pass.

Failure stops the lane before native compilation.

## Gate 2: four-card changed-input component

Use the prior routed-W1 gate design, revised and sealed for literal N32. Run
independently on all four physical B70s with exact source and installed-binary
identity. Before and after timing, changing epochs must compare candidate
against N64 bitwise through:

- raw local W1 BF16 output;
- BF16 SiLU output;
- unchanged N64 W2 output;
- fixed-order gathered/final output;
- input immutability and candidate repeat determinism; and
- remote-route scratch behavior.

The trace must prove candidate N32 W1 dispatch, incumbent N64 W2 dispatch, and
no N32 dispatch for M=1 through M=7.

Timing uses frozen A-B-B-A blocks with synchronization only at arm boundaries.
Every card must save at least `0.20 ms` per complete 47-layer routed-W1 cycle
and win the preregistered block-count guard. Aggregate mean relative W1 time
must improve by at least 2%. These are promotion floors, not performance
claims.

Any bit difference, dispatch ambiguity, per-card timing failure, physical-card
identity failure, or artifact mismatch closes the lane. No endpoint may be
started.

## Gate 3: cold counters

Only a complete Gate-2 pass authorizes construction and preregistration of a
dedicated cold-counter comparison. It must use matched N64/N32 pairs on all
four cards and require:

- candidate wins in every preregistered pair;
- no card-level slowdown in W1 elapsed time;
- consistent useful XVE/occupancy movement without a compensating bandwidth,
  stall, or launch regression; and
- bitwise post-counter replay.

Counter failure is terminal, as it was for the shared-expert lanes. Component
timing alone does not authorize model generation.

## Gate 4: graph diagnostic

Only passing counters authorize a no-promotion diagnostic on the current
persistent-metadata Breakable graph stack. It must preserve:

- one active generation;
- exact q1/eager/graph token identity on a fresh cold request;
- `cached_tokens=0`;
- DFlash depth seven and bounded acceptance drift;
- the audited 146-graph/145-break topology with 48 attention and 97
  collective boundaries on all four ranks; and
- unchanged vLLM source and all selectors except literal W1 tile 64 versus 32.

The diagnostic must show a positive whole-replay and target-cycle effect. A
component-only saving or host-timing shift is insufficient.

## Gate 5: frozen endpoint campaign

Only Gates 1 through 4 may authorize construction, audit, and commit of a
fresh graph-vs-graph endpoint harness. The campaign order is fixed:

1. A1: N64;
2. B1: N32;
3. B2: N32 only after the frozen phase-one gates pass; and
4. A2: N64.

Each leg uses a new service and unique NVMe artifact root. There is no
generation warmup, retry, rescue leg, retained service, fifth run, repeated
prompt, prefix/KV cache reuse, response reuse, history/ngram acceleration, or
concurrent request.

Every executed leg must be canonical-q1 bitwise exact 13/13, cache-zero 13/13,
long-then-next exact 2/2, rollover exact 1/1, cleanly stopped, and followed by
four-device idle proof. Both adjacent candidate/control comparisons must pass
the existing causal gates: candidate headline win, at least 9/13 paired row
wins, positive paired median, positive target-cycle saving, and absolute
acceptance-rate drift no greater than 0.001.

Only the lower of B1 and B2 may be promoted, and only if it is strictly above
`94.92003934159611 tok/s` with every identity, honesty, quality, causal, and
cleanup gate intact. Exactness without a robust endpoint win is a preserved
negative or inconclusive result, not a submission.

## Publication boundary

No LocalMaxxing payload may be created or submitted before the full formal
campaign passes and an independent raw-artifact audit approves the
conservative candidate. If it passes, submit only the conservative lower
candidate through the credential-safe helper and record the response without
exposing the API key.
