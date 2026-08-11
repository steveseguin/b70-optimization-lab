# 2026-08-11 BF16 Maximum-Performance Campaign (Lanes H-M + Deploy)

Operator directive: maximize BF16 performance across all four B70s without
hurting quality. Baseline entering: 2-card BF16 + kquant dflash n5 p0.1 =
22.6/33.6/30.0 (avg 28.7), no-spec 9.85. Raw JSONL under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/` (laneH..laneM).

## What was tried, in order

| Lane | Lever | Result |
| --- | --- | --- |
| probe | `-sm row` 2-card BF16 | segfault at load. Row split is a permanent NO-GO on this stack (Q8 crashed identically). |
| H | 4-card layer split | no-spec 7.67 (worse than 2-card 9.85: more hops); dflash n5 27.7 avg. 4-card loses per-request AND aggregate. 2-card confirmed. |
| I | kquant-drafter fine grid | new kquant champion n6 p0.1: 23.5/34.5/34.0 (avg 30.7, +7% over n5). n7 flat, p_min 0.05-0.15 flat. |
| K | runtime toggles (graph/dnn/opt off, p 0.05) | all neutral. Config knobs exhausted. |
| conv | BF16 drafter | `dflash-bf16.gguf` (5.12 GB) converted from `meta-models/Muse-Glimmer-30B-assistant` via `convert_hf_to_gguf.py --target-model-dir` (target config+tokenizer staged separately). |
| J | BF16 drafter ladder | depth curve INVERTED: n5 29.0 -> n15 34.9 avg. Champion **n15 p0.2 = 24.3/37.7/42.7** (block-16 cap). BF16 drafter block pass is cheap enough that maximum-depth blocks pay. |
| L | n15 p_min refine | p 0.1/0.15/0.3 and n12 all at-or-below n15 p0.2. Final. |
| M | champion determinism | acceptance counts vary run-to-run (drafter forward nondeterministic); only json byte-stable across repeats. Full replay remains a no-spec-only property. |
| prefill | ub ladder, 18K prompt | 1024: 1042 tok/s; **2048: 1162 (+11.5%)**; 4096: 1144. 18K-context decode holds ~29. Long-context retrieval exact via chat endpoint. |

## Exactness map (BF16 target, greedy)

- no-spec: fully deterministic, all classes (the exact-replay identity).
- kquant or BF16 drafter, any depth: 2-of-3 classes byte-exact vs no-spec;
  which classes depends on verify batch size (batch-vs-single numerics).
- Every accepted token is the target's argmax under a valid batched
  forward; divergences are near-tie flips only. Quality preserved;
  byte-replay across the spec path needs kernel source work (later lane).

## Production deployment (live)

Asymmetric two-lane fleet (single slot each), frontdoor :8000 with new
modality routing (`FRONTDOOR_VISION_BACKEND_INDICES`, image payloads pin
to vision-capable backends; patch in `openai-lan-frontdoor.py`):

- TEXT lane :19470 (GPUs 0+1): BF16 drafter n15 p0.2, no mmproj, ub 1024.
  Measured in production: 41.8 tok/s json canary.
- VISION lane :19471 (GPUs 2+3): kquant drafter n6 p0.1 + BF16 mmproj,
  ub 1024. Measured: 33.6 tok/s json canary; color canaries pass.
- Frontdoor c2: 54.7 tok/s aggregate (37.4 + 27.4 with TTFT).

Deploy incident (recorded): text lane at ub 2048/c 65536 overflowed card0;
GGML_SYCL host-mem fallback silently spilled weights to system RAM ->
1.10 tok/s with normal acceptance. Detection: card0 resident 7 GB.
Rule: after any fleet config change, check per-card residency AND a decode
canary; host-fallback hides fit failures. ub 2048 is safe only at c 32768
in the sweep harness shape; production keeps ub 1024.

## Final ledger (json class, per replica)

| Stage | tok/s |
| --- | --- |
| BF16 no-spec | 9.85 |
| + kquant dflash n5 p0.1 (day-1) | 30.0 |
| + n6 p0.1 grid | 34.0 |
| + BF16 drafter, n15 p0.2 | **42.7 (4.34x no-spec)** |

Prose 24.3 (2.47x), code 37.7 (3.83x). All lossless-BF16.

## Remaining levers (source work, ranked)

1. Batched-verify/single-step numeric unification -> full byte-exact spec
   replay (and record-gate eligibility for the spec identity).
2. Drafter-forward determinism (same goal, drafter side).
3. Cross-card drafter tensor mirroring -> mmproj + BF16 drafter coexist;
   also unlocks single-card-target shapes for other quants.
4. k-quant batched-verify kernels -> revives the 4x1-card dynamic fleet
   (~109 -> 180-220 aggregate) as a throughput alternate.
