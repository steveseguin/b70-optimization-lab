# Laguna exact-small portfolio: fresh post-recovery smoke

Date: 2026-08-02 America/Toronto

Status: **preregistered; one new non-scored TP4 2x400 smoke is authorized only
after the corrected harness, this packet, and a non-self-referential execution
lock are committed. No endpoint is authorized by this packet.**

Steve explicitly asked to continue optimizing on 2026-08-02. This packet
selects the strongest component-positive decode candidate that still lacks a
model result. It is a new current-boot gate after the sealed recovery and two
later operationally clean TP4 starts/teardowns; only the scheduler control was
repeat-oracle exact. It is not a retry under the consumed 2026-08-01 smoke
authorization.

## Why this candidate and why a new harness

The exact-small portfolio passed its frozen real-shape component gate with all
12 raw-BF16 comparisons exact and immutable inputs. Direct measured saving was
`0.3082524 ms/cycle` against a `0.3000000 ms/cycle` threshold. The projection
is roughly `126.7 tok/s` from the protected `125.4619731637751 tok/s`
conventional record, but that is not endpoint evidence.

The first authorized smoke stopped inside XCCL initialization before model
loading or any request. A later audit found an independent harness defect:
the 47-argument runner exported the mapped-tail selector but did not export
the grouped-GEMM no-K-loop-barrier or scale-lane-dedup selectors through its
`env -i` service launch. Had that service reached a request, it would have
measured only the mapped tail, not the three-part portfolio. Because no request
ran, no candidate result is reclassified; the failed root remains valid host
failure evidence.

The amended runner adds literal/default-off arguments 48 and 49, records and
checks both in the API and all four worker environments, and requires them on
together with mapped tail, M12/DFlash11, GRF128, transposed scales, scale
vectorization, literal scale-fold zero, and literal dequant-MAD zero. The smoke
also sets `LAGUNA_LOG_MOE_ROWS=1` and requires exactly one rank-local
`num_rows=12` marker on each TP/EP rank.

There is no runtime log carrying the C++ class name
`GemmCuteGrf128ExactSmallPortfolioName`. Combined dispatch evidence is
therefore deliberately inferential and frozen before execution:

1. exact clean XPU-kernel commit and exact candidate DSO hash;
2. the static source route that selects the separately named combined kernel
   only when both selectors are true at the real M12 W13/W2 shapes;
3. both selectors and every prerequisite in the API plus all four worker
   environments;
4. the candidate grouped-GEMM DSO mapped at its exact path/hash in every
   worker;
5. four-rank `num_rows=12` evidence and four-rank mapped-tail enable/dispatch
   evidence during real requests.

No DSO rebuild is authorized merely to add a log marker.

## Frozen source, runtime, and model identity

- vLLM worktree:
  `/home/steve/src/laguna-vllm-exact-small-portfolio-20260801`, clean commit
  `0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d`;
- XPU-kernel worktree:
  `/home/steve/src/laguna-xpu-kernels-exact-small-portfolio-20260801`, clean
  commit `46a6393fc188c11661ddab9cf1320d2f3de45087`;
- runtime lock: `data/laguna-exact-small-portfolio-runtime-lock-20260801.json`,
  SHA-256
  `42e50b479b9ecc31db63998cd1b7bfe5cb7865ee38ed80516232bc9428765836`;
- `_C.abi3.so` SHA-256
  `36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095`;
- `_moe_C.abi3.so` SHA-256
  `51a1f2b02fc8a21e420edfff79c30ff0f2170d4bab0b6b1efb25d1f79b1f8a66`;
- `libgrouped_gemm_xe_2.so` SHA-256
  `5d2d29e63f40c62d31b61808d74a0ef7ba71f2c6a62754c3220ed4d0c8281d4b`;
- exact grouped route source SHA-256
  `7adf11249f8299c6d8a696156423244901330d69315e14a1c20eb676fb246a9f`;
- target revision `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft revision `5e07c246915c86dc6920fead03d019989224f2ba`;
- model-manifest SHA-256
  `45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac`;
- fixed realistic suite SHA-256
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`;
- canonical q1 teacher SHA-256
  `d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1`.

All additional Python, runtime, and native objects remain pinned by the runtime
lock and measurement runner.

## Frozen model and selector identity

- TP4+EP4, one active sequence, no PP/DP expansion;
- exact M12 target verifier and DFlash depth 11;
- BF16 target and draft KV;
- max model length and batched-token limit `8192/8192`;
- GPU memory utilization `0.90`;
- PIECEWISE target capture size 12, target `146/145`, draft `14/13`;
- async scheduling and prefix caching off;
- installed locked oneCCL, `public_oneccl=0`;
- M8 shared elementwise off, exact M12 shared elementwise on;
- Q/K RMSNorm plus RoPE on;
- width-12 router and DFlash context-KV workspace stack on;
- 31 DFlash draft projections use the established FP8 W8A16 path; target and
  draft KV remain BF16, and no target projection changes precision;
- segmented DFlash plus inline DFlash attention on;
- decode GRF128, transposed scales, scale vector, mapped tail, no-K-loop
  barriers, and scale-lane dedup on;
- scale fold, dequant MAD, rank-sum/RMSNorm, target inline gathers, all
  other diagnostic probes, and unrelated selectors off;
- one service, exactly two unique suite requests, 400 output tokens each, no
  warmup, no retry, and no score.

The frozen positional tail is `... M12_MAPPED_TAIL=1,
DECODE_NO_KLOOP_BARRIERS=1, SCALE_LANE_DEDUP=1`. The dedicated wrapper builds
and self-checks all 49 arguments; its static and negative tests must pass before
the execution lock is created.

Pre-lock offline validation passed before any model action:

- 14/14 candidate-kernel static contracts;
- 3/3 focused vLLM mapped-tail integration tests;
- 9/9 executable CPU-only harness tests, with the execution-lock check
  intentionally skipped until the lock exists;
- Bash syntax and whitespace checks;
- Ruff checks for the new test and the reused Python smoke/idle helpers.

The harness suite covers malformed and half-enabled grouped selectors, wrong
treatment/M/spec/shared/mapped/width/GRF128/transposed-scale dependencies,
empty scale prerequisites, the exact 49-argument vector, environment/DSO/row
proof wiring, and the outer host, journal, memory, swap, interface, and service
guards.

## Current-boot and resource boundary

The sealed recovery packet is
`data/laguna-device-recovery-scheduler-gate-20260802.json`; all four one-shot
device probes and the corrected TP4 collective passed on boot
`ee67272f-9fee-41cf-9a37-b9eaa438a5cf`. The subsequent scheduler A/B loaded and
ran two complete TP4 models, then produced the current PASS_IDLE host packet
`data/laguna-scheduler-alignment-postpair-host-20260802.json`. This evidence is
readiness context, not a scheduler-treatment dependency or execution-lock
input. Recovery/current-boot and live fail-closed checks stand independently.
The later operational evidence is stronger and less invasive than another
device probe, so no new XPU probe, reset, FLR, driver reload, reboot, or
shared-state cleanup is authorized.

The wrapper must fail closed on boot/kernel/taint drift, BDF/vendor/device/xe or
DRM-binding drift, a foreign DRM opener, model process, protected listener,
active Gemma unit, or device-error journal match. `eno1` must carry
`10.0.0.65`. The only swap is ordinary `/swap.img:8388604`; no long-context
temporary swap may exist or be created.

At 1 Hz through the model leg, stop below `8,388,608 kB` MemAvailable, or when
MemAvailable is below `16,777,216 kB` while SwapFree is below `4,194,304 kB`.
Preserve the complete samples and any alarm. Pre/post host snapshots, the
kernel journal from sealed recovery completion, bounded service cleanup, the runner's
60-second pre/post idle intervals, and all raw failure evidence are mandatory.

## Pass, stop, and next authorization

The smoke passes only if all of the following hold:

- 2/2 token prefixes match the canonical q1 teacher and both rows are
  cache-zero with request-local speculation;
- target `146/145` and draft `14/13` capture and replay occur on all four ranks;
- mapped-tail enable and dispatch markers occur on all four ranks;
- both grouped selectors and exact prerequisites occur in the API and all four
  worker environments;
- the exact grouped DSO path/hash occurs in all four worker maps;
- real M12 row evidence occurs on all four ranks;
- the service, workers, RPC path, listener, DRM openers, host memory, kernel
  journal, and 60-second post-idle gate are clean.

Any failure consumes this one smoke and stops. Preserve it without retry or
metric interpretation. A complete pass authorizes only drafting and committing
a separate first-result cold 13x512 endpoint preregistration and execution
lock plus an explicit amendment removing the generic runner's smoke-only guard.
It does not itself authorize that endpoint, report throughput, or submit to
LocalMaxxing.

After the harness commit and a separate lock-only commit, the only authorized
entry point is:

```bash
experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_postrecovery.sh \
  20260803T010333Z
```

The lock binds that exact tag and its exact campaign/smoke roots. A stable
repository mutex prevents concurrent campaigns, and atomic campaign-root
creation consumes the one-shot authorization. Every other tag and every reused
root fails before model action. The campaign and smoke roots are fresh children
of the local NVMe run root and are sealed read-only on every terminal path.
